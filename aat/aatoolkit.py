
import os
import json
import jsonlines
import requests
from autogen.agentchat.contrib.retrieve_user_proxy_agent import RetrieveUserProxyAgent

from datetime import datetime
from anthropic import Anthropic

client = Anthropic(
    # This is the default and can be omitted
    api_key=os.environ.get("ANTHROPIC_API_KEY"),
)

from aat.rag import rag_chat

def generate_prompt(project_background, research_paper):

    messages = [

        {
            "role": "user",
            "content": f"""
                [MY BACKGROUND]
                {project_background}


                [RESEARCH PAPER]
                {research_paper}

                respond in json only
            """,
        },
    ]
    return messages

class ResearchAssistant:
    def __init__(self, context_file_path="./README.md", data_folder="./data", model=""):
        self.context_file_path = context_file_path
        self.data_folder = data_folder
        self.model = model

        with open(context_file_path, "r") as f:
            self.project_context = f.read()

        self.project_context = "I'm an AI alignment researcher. I'm working on on a project to find novel solution to solve AI alignment"
        self.log_folder = os.path.join(data_folder, "log")
        self.article_discussion_folder = os.path.join(data_folder, "article_discussion")

        if not os.path.exists(data_folder):
            os.makedirs(data_folder)
        if not os.path.exists(self.log_folder):
            os.makedirs(self.log_folder)
        if not os.path.exists(self.article_discussion_folder):
            os.makedirs(self.article_discussion_folder)

        self.articles_file_path = os.path.join(data_folder, "articles.jsonl")

    def update_rag_vectors(self, articles):
        if not os.path.exists("tmp"):
            os.makedirs("tmp")

        for article in articles:
            with open(f"tmp/{article['id']}.txt", "w") as f:
                f.write(article["text"])
        docs_path = [f"tmp/{article_file}" for article_file in os.listdir("tmp") if article_file.endswith(".txt")]

        ragproxyagent = RetrieveUserProxyAgent(
            name="ragproxyagent",
            code_execution_config=False,
            retrieve_config={
                "task": "qa",
                "docs_path": docs_path,
                # "chunk_mode": "one_line",
            },
        )

    def discussion_with_article(self, article_id):


        print(f"start article discussion for article {article_id}")

        with jsonlines.open(self.articles_file_path) as reader:
            articles = [item for item in reader]

        article = None
        for item in articles:
            if item["id"] == article_id:
                article = item
                break

        if not article:
            raise Exception("Article not found")
        
        res = rag_chat(self.project_context, article["text"][0:30000])
        text = f"## {article['title']}\n\n article_id: {article['id']}\n\n url:{article['url']} \n\n"

        for history in res.chat_history[1:]:
            role = "Advisor" if history["role"] == "user" else "Researcher"
            text += f"### {role}\n"
            text += f"{history['content']}\n\n"

        with open(os.path.join(self.article_discussion_folder, f"{article['id']}.md"), "wt") as f:
            f.write(text)

        print(f"done discussion {article_id}")


    def check_latest_papers(self):
        '''
            goes throuth all uncategorized papers and categorizes them.
            it will mark papers categorized after that
        '''
        last_date_published = '2020-01-01T00:00:00Z'
        if os.path.exists(self.articles_file_path):
            with jsonlines.open(self.articles_file_path) as reader:
                current_articles = [item for item in reader]
                if len(current_articles) > 0:
                    last_date_published = current_articles[-1]["date_published"]

        print("last_date_published", last_date_published)
        print("start fetching articles")

        res = requests.get("http://localhost:4001/db/query?pretty&timings&associative", params={
            "q": f"select * from articles where date_published > '{last_date_published}' order by date_published asc limit 10"
        })

        rows = res.json()["results"][0]["rows"]

        print("fetched articles", len(rows))

        print("start scoring article relevancy")

        instructions = """
            You are a helpful AI reserach assistant.
            Given that I'm a researcher in AI alignment, and this background (text below [MY BACKGROUND]) of my project and this research paper (text below [RESEARCH PAPER]).
            relevency: 0 being not relevant at all, 10 being direclty extremely relevant to my project
            justification: reasons to justify why you gave the score
            Please provide the answer in JSON format. Ensure the JSON is correctly structured and properly formatted. Here is an example structure for reference:
            {
                "relevancy": 5
                "justification": "..."
            }
        """

        relevant_articles = []
        for article in rows:
            relevancy = client.messages.create(
                max_tokens=4096,
                messages=generate_prompt(self.project_context, article["text"][0:30000]),
                model="claude-3-haiku-20240307",
                system=instructions
            )
            try:
                relevancyj = json.loads(relevancy.content[0].text)
            except:
                print("error parsing relevancy", relevancy.content[0].text)
                continue
            article["relevancy"] = relevancyj["relevancy"]
            article["relevancy_justification"] = relevancyj["justification"]

            if article["relevancy"] > 5:
                relevant_articles.append(article)

            with jsonlines.open(self.articles_file_path, mode='a') as writer:
                    writer.write(article)
        print(f"done scoring article relevancy {len(relevant_articles)} articles above score 5 of relevancy")

        logoutput = {
            "task": "relevancy",
            "last_date_published": last_date_published,
            "new_last_date_pulished": rows[-1]["date_published"],
            "articles": [{
                "id": row["id"],
                "title": row["title"],
                "date_published": row["date_published"],
                "relevancy": row.get("relevancy"),
                "relevancy_justification": row.get("relevancy_justification")
            } for row in rows]
        }

        now = datetime.now()
        with open(os.path.join(self.log_folder, f"{now}.json"), "w") as f:
            json.dump(logoutput, f)

        print(f"start article discussions for relevant articles")

        for article in relevant_articles:
            self.discussion_with_article(article["id"])
