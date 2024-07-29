
import os
import autogen
from autogen import AssistantAgent
# claude-3-5-sonnet-20240620
# claude-3-haiku-20240307
config_list = [{
    "model": "claude-3-5-sonnet-20240620",
    "api_key": os.getenv("ANTHROPIC_API_KEY"),
    "api_type": "anthropic"
}]

def termination_msg(x):
    return isinstance(x, dict) and "TERMINATE" == str(x.get("content", ""))[-9:].upper()

llm_config = {"config_list": config_list, "timeout": 60, "temperature": 0.8, "seed": 1234}

 
def rag_chat(project_context, paper):
    PROBLEM = f"""
    Give me ideas how I can use the findings of the research paper to help with my project.
    
    [My project]
    {project_context}

    [Research Paper]
    {paper}

    [Your answer]
    The key findings of the research paper are:
    * 
    *
    * 

    You research paper could benefit by
    * 
    * 
    * 
    """

    advisor = AssistantAgent(
        name="advisor",
        # is_termination_msg=termination_msg,
        # default_auto_reply="Reply `TERMINATE` if the task is done.",
        code_execution_config=False,
        description="You are a helpful AI research advisor. You are very demanding. Give a lot of suggestions.",
        llm_config={"config_list": config_list, "timeout": 60, "temperature": 0.7},
    )

    researcher = AssistantAgent(
        name="researcher",
        # is_termination_msg=termination_msg,
        # default_auto_reply="Reply `TERMINATE` if the task is done.",
        code_execution_config=False,
        description="You are an AI researcher trying to solve AI alignment. You are talking to you research advisor. Ask a lot of questions and try to get most out of him/her.",
        llm_config={"config_list": config_list, "timeout": 60, "temperature": 0.7},
    )

    advisor.reset()
    researcher.reset()

    groupchat = autogen.GroupChat(
        agents=[advisor, researcher], messages=[], max_round=7, speaker_selection_method="round_robin"
    )
    manager = autogen.GroupChatManager(groupchat=groupchat, llm_config=llm_config)

    # Start chatting with boss_aid as this is the user proxy agent.
    return researcher.initiate_chat(
        manager,
        message=PROBLEM[0:30000],
        n_results=3,
        silent=True,
    )
