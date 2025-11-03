""" Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. """
""" SPDX-License-Identifier: MIT-0 """

import os
import json
import boto3
import requests
import base64

from typing import Dict, List, Any
from botocore.exceptions import ClientError
from requests.auth import HTTPBasicAuth
from aws_lambda_powertools import Tracer
from aws_lambda_powertools import Logger

# Environmental parameters
TEXT_MODEL_ID = os.environ["TEXT_MODEL_ID"]
EMBEDDING_MODEL_ID = os.environ["EMBEDDING_MODEL_ID"]
OPENSEARCH_ENDPOINT = os.getenv("OPENSEARCH_ENDPOINT", None)
OPENSEARCH_SECRET = os.getenv("OPENSEARCH_SECRET", None)
OPENSEARCH_INDEX = os.getenv("OPENSEARCH_INDEX", None)

# Global parameters
tracer = Tracer()
logger = Logger()
bedrock_client = boto3.client("bedrock-runtime")
polly_client = boto3.client("polly")

@tracer.capture_lambda_handler
def lambda_handler(event, context): 
    logger.info(f"Received event: {json.dumps(event, indent=2)}")
    body = json.loads(event["body"])
    validate_response = validate_inputs(body)
    if validate_response:
        return validate_response
    question = body["question"]
    # if the voice_id or voice_engine isn't specified, use default values
    voice_id = body.get("voice_id", "Ruth")
    voice_engine = body.get("voice_engine", "neural")
    logger.info(f"Question: {question}")
    logger.info(f"Voice ID: {voice_id}")
    logger.info(f"Voice Engine: {voice_engine}")

    response = get_prediction(question=question)
    speech_info = synthesize_speech(text = response, 
        voice_id = voice_id,
        voice_engine = voice_engine)

    return build_response(
        {
            "response": response,
            "speech_info" : speech_info            
        }
    )

def synthesize_speech(text: str, voice_id: str, voice_engine: str):
    # given text to synthesize along with the voice ID and engine, this will 
    # get a buffer with the pcm in 1 channel 16-bit at 16k and then will
    # get a buffer with json that has all of the viseme timings
    speech_info = {}
    
    try:
        sound_response = polly_client.synthesize_speech(
            OutputFormat = "pcm",
            Text = text,
            VoiceId = voice_id,
            Engine = voice_engine
        )
        audio_stream = sound_response["AudioStream"]
        speech_info['sound_status'] = "ok"
        speech_info['sound_response'] = base64.b64encode(audio_stream.read()).decode("utf-8")
    except Exception as e:
        speech_info['sound_status'] = "error"
        exception_str = f"Audio Exception: {type(e).__name__} Message: {str(e)}"
        speech_info['sound_error'] = exception_str
        logger.info(exception_str)
    
    try:
        viseme_response = polly_client.synthesize_speech(
            OutputFormat = "json",
            SpeechMarkTypes = ["viseme"],
            Text = text,
            VoiceId = voice_id,
            Engine = voice_engine
        )
        viseme_strem = viseme_response["AudioStream"]
        speech_info['viseme_status'] = "ok"
        speech_info['viseme_response'] = base64.b64encode(viseme_strem.read()).decode("utf-8")
    except Exception as e:
        speech_info['viseme_status'] = "error"
        exception_str = f"Viseme Exception: {type(e).__name__} Message: {str(e)}"
        speech_info['viseme_error'] = exception_str
        logger.info(exception_str)
    
    return speech_info

def build_response(body: Dict) -> Dict:
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(body)
    }


def validate_inputs(body: Dict):
    for input_name in ["question"]:
        if input_name not in body:
            return build_response(
                {
                    "status": "error",
                    "message": f"{input_name} missing in request payload"
                }
            )


def verify_index(endpoint: str, index: str, username: str, password: str) -> Any:
    url = f"{endpoint}/{index}"
    response = requests.head(url, auth=HTTPBasicAuth(username, password), timeout=10)
    if response.status_code != 200:
        logger.info("Embedding index unavailable. RAG data ingest required.")
        return build_response(
            {
                "status": "error",
                "message": "The vector store is not yet hydrated, and cannot be queried for context. Please contact your System Administrator to ingest RAG data."
            }
        )


def get_credentials(secret_id: str, region: str) -> str:
    client = boto3.client("secretsmanager", region_name=region)
    try:
        response = client.get_secret_value(SecretId=secret_id)
        json_body = json.loads(response["SecretString"])
        return json_body["USERNAME"], json_body["PASSWORD"]
    except ClientError as e:
        message = e.response["Error"]["Message"]
        logger.error(message)
        return build_response(
            {
                "status": "error",
                "message": message
            }
        )


def get_embedding(passage: str) -> List[float]:
    body = json.dumps(
        {
            "inputText": f"{passage}"
        }
    )
    try:
        request = bedrock_client.invoke_model(
            body=body,
            modelId=EMBEDDING_MODEL_ID,
            accept="application/json",
            contentType="application/json"
        )
        response = json.loads(request.get("body").read())
        embedding = response.get("embedding")
        return embedding
    except ClientError as e:
        message = e.response["Error"]["Message"]
        logger.error(message)
        return build_response(
            {
                "status": "error",
                "message": message
            }
        )


def get_hits(query: str, url: str, username: str, password: str) -> List[dict]:
    k = 3  # Retrieve Top 3 matching context from search
    search_query = {
        "size": k,
        "query": {
            "knn": {
                "vector_field": { # k-NN vector field
                    "vector": get_embedding(query),
                    "k": k
                }
            }
        }
    }
    response = requests.post(
        url=url,
        auth=HTTPBasicAuth(username, password),
        json=search_query,
        timeout=10
    ).json()
    hits = response["hits"]["hits"]
    return hits


def get_prediction(question: str) -> str:
    region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION"))
    domain_endpoint = f"https://{OPENSEARCH_ENDPOINT}" if not OPENSEARCH_ENDPOINT.startswith("https://") else OPENSEARCH_ENDPOINT

    logger.info(f"Retrieving OpenSearch credentials ...")
    username, password = get_credentials(OPENSEARCH_SECRET, region)
    
    logger.info("Verifying embedding index exists ...")
    verify_response = verify_index(endpoint=domain_endpoint, index=OPENSEARCH_INDEX, username=username, password=password)
    if verify_response:
        return verify_response
    search_url = f"{domain_endpoint}/{OPENSEARCH_INDEX}/_search"
    
    logger.info(f"Embedding index exists, retrieving query hits from OpenSearch endpoint: {search_url}")
    hits = get_hits(query=question, url=search_url, username=username, password=password)
    
    logger.info("The following documents were returned from OpenSearch:")
    for hit in hits:
        logger.info(f"Score: {hit['_score']} | Document: {hit['_source']['file_name']} | Passage: {hit['_source']['passage']}\n")
    
    logger.info(f"Sending prompt to Bedrock (Using OpenSearch context) ...")
    context = hits[0]['_source']['passage'] # Top hit from search
    prompt_template = f"""\n\nHuman: Your name is Ada, and you are a helpful assistant, helping a Human answer questions with the tone of a stereotypical pirate. Use the following as additional context to provide a concise answer to the question at the end, but don't say that you're using additional context.

    <reference>
    {context}
    </reference>
    
    Question: {question}\n\nAssistant:"""
    response = bedrock_client.invoke_model(
        body=json.dumps(
            {
                "prompt": prompt_template,
                "max_tokens_to_sample": 200,
                "anthropic_version": "bedrock-2023-05-31"
            }
        ),
        modelId=TEXT_MODEL_ID,
        accept="*/*",
        contentType="application/json"
    )
    response_body = json.loads(response.get("body").read())
    answer = response_body.get("completion")
    logger.info(f"Bedrock returned the following answer: {answer}")
    return answer
