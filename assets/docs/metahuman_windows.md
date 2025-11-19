# Install Unreal Engine 5.4 on Windows 2022

## Prerequisites

1. Ensure you have ~50GB of available disk space for the installation.
2. Download and run the ___Visual Studio 2022 (Community Edition)___ installer. See [Setting Up Visual Studio for Unreal Engine](https://docs.unrealengine.com/5.4/en-US/setting-up-visual-studio-development-environment-for-cplusplus-projects-in-unreal-engine/) for more information.
    - Select ___Game development with C++___ under ___Workloads___.
    - Under ___Optional___, make sure the checkbox for ___Unreal Engine installer___ is checked to enable it.

## Unreal Engine 5.4 Installation

1. Run the ___Epic Games Launcher___, by double-clicking on the desktop icon.
2. Sign into your ___Epic Games___ account. 
3. Select ___Unreal Engine___ in the left-hand navigation panel, and click on the ___Library__ tab. 
4. Click the ___ENGINE VERSIONS___ "plus" option, and select ___5.4___ from the version drop-down.
5. Click the ___Install___ button.
6. Accept the default installation locations, and click ___Install___.

## Configure the MetaHuman Project

1. Download the [MetaHuman](https://artifacts.kits.eventoutfitters.aws.dev/industries/games/AmazonPollyMetaHuman.zip) sample project.
2. Extract the `AmazonPollyMetaHuman` folder.
3. Right-click on the `AmazonPollyMetaHuman.uproject` file and select `Generate Visual Studio project files`.
4. Open the `AmazonPollyMetaHuman.sln` file in Microsoft Visual Studio 2022.
5. In Visual Studio, navigate to `Source/AmazonPollyMetaHuman/Private/SpeechComponent.cpp` and open it for editing.
6. Locate the `CallAPI` function and update the placeholder URLs with your API endpoints from CloudFormation:
    ```cpp
    void USpeechComponent::CallAPI(const FString Text, const FString Uri)
    {
        FString ComboBoxUri = "";
        FHttpRequestRef Request = FHttpModule::Get().CreateRequest();
        UE_LOG(LogPollyMsg, Display, TEXT("%s"), *Uri);
        if(Uri == "Regular LLM")
        {
            UE_LOG(LogPollyMsg, Display, TEXT("If Regular LLM"));
            ComboBoxUri = "<ADD TextApiEndpointUrl VALUE FROM CLOUDFORMATION>";
        } else {
            UE_LOG(LogPollyMsg, Display, TEXT("If Else"));
            
            ComboBoxUri = "<ADD RagApiEndpointUrl VALUE FROM CLOUDFORMATION>";
        }
    ```
7. Save the file.
8. In Visual Studio, select `Build` --> `Build Solution` to compile the project.
9. Once the build completes successfully, close Visual Studio.
10. Open the `AmazonPollyMetaHuman.uproject` file to launch Unreal Engine.
11. Click the `Play` button to interact with the Ada NPC.