import os
import logging

from bs4 import BeautifulSoup
import requests
import google.generativeai as genai
from dotenv import load_dotenv

from gmail_client import GmailClient
from utilities import read_email_data
from utilities import Scraper
from utilities import DataBase
from utilities import LLM_Client


load_dotenv("./API_raktas.env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
MODEL = genai.GenerativeModel("gemini-1.5-flash-8b")

URL = "https://15min.lt/"  # padaryti kintamuosius didziosioms raidem
ROBOTS_TXT = URL + "robots.txt"
PATH_TO_EMAIL_TEMPLATE = "./mail_duomenys.txt"


logging.basicConfig(level=logging.INFO)

PROMPT_SEO = """
You are experienced SEO professional. I will provide you with web page heading and text. You should provide suggestions 
how heading could be improved.

INPUT: {text}
You should provide an answer is following JSON format:
{{
"heading": <original heading>
"your_suggestion": <your suggestion>
}}
"""

PROMPT_WORD = """
You are experienced SEO professional. Please find mistakes in the text and suggest corrections for incorrect words. 
Please check only grammer mistakes. Please double-check if you have actually found a mistake before providing the final answer.

Think step by step: 
1. Found initial mistakes
2. Ensure that your suggestion is not the same as an original word.
3. Ensure that this error readly valid.
4. If no grammatical error found and the word itself is grammatically correct, don not include this word in the output.
5. Ensure that the suggested correction is different from the original word.

return only valid JSON without additional text.

INPUT: {text}
You should provide an answer is following JSON format:
{{
"original_word": "<original word with mistake>",
"suggested_correction": "<corrected version>",
"reasoning": "<reasoning>"
}}
"""

ANTRASCIU_STRUKTURA_CREATE_QUERY = """
            CREATE TABLE IF NOT EXISTS antrasciu_struktura (
                heading TEXT,
                your_suggestion TEXT
            )
        """
TEKSTO_KOREKCIJOS_REKOMENDACIJOS_CREATE_QUERY = """
                CREATE TABLE IF NOT EXISTS teksto_korekcijos_rekomendacijos (
                    original_word TEXT,
                    suggested_correction TEXT,
                    reasoning TEXT
                )
            """

INSERT_INTO_ANTRASCIU_STRUKTURA_QUERY = "INSERT INTO antrasciu_struktura (heading, your_suggestion) VALUES ('{heading}', '{suggestion}')"
INSERT_INTO_TEKSTO_KOREKCIJOS = "INSERT INTO teksto_korekcijos_rekomendacijos (original_word, suggested_correction, reasoning) VALUES ('{original_word}', '{suggested_correction}', '{reasoning}')"

gmail_client = GmailClient()
web_scraper = Scraper()
db = DataBase()
llm = LLM_Client()

db.execute_query("heading_database.db", ANTRASCIU_STRUKTURA_CREATE_QUERY)
db.execute_query("webpage_database.db", TEKSTO_KOREKCIJOS_REKOMENDACIJOS_CREATE_QUERY)


url_response_robots = requests.get(ROBOTS_TXT)
web_scraper.file_exist(response=url_response_robots, file_name="robots.txt")

url_response = requests.get(URL)
url_soup = BeautifulSoup(url_response.text, "html.parser")

url_antrastes = url_soup.find_all("h1")
description, keywords = web_scraper.extract_meta(url_soup)
get_headings_info = web_scraper.extract_headings_and_content(url_response.text)

seo_llm_response = MODEL.generate_content(PROMPT_SEO.format(text=get_headings_info))
heading_text_list = llm.clean_text_list(
    text=seo_llm_response.text, prompt=(PROMPT_SEO.format(text=get_headings_info))
)

url_text = url_soup.get_text()

clean_text = " ".join(url_text.split())

word_llm_response = MODEL.generate_content(PROMPT_WORD.format(text=clean_text))
corection_text_list = llm.clean_text_list(
    text=word_llm_response.text, prompt=(PROMPT_WORD.format(text=clean_text))
)

if corection_text_list and heading_text_list:
    for text in heading_text_list:
        query = INSERT_INTO_ANTRASCIU_STRUKTURA_QUERY.format(
            heading=text["heading"], suggestion=text["your_suggestion"]
        )
        db.execute_query(database="heading_database.db", query=query)

    for text in corection_text_list:
        query = INSERT_INTO_TEKSTO_KOREKCIJOS.format(
            original_word=text.get("original_word", "").replace("'", ""),
            suggested_correction=text.get("suggested_correction", "").replace("'", ""),
            reasoning=text.get("reasoning", "").replace("'", ""),
        )
        db.execute_query(database="webpage_database.", query=query)
else:
    logging.info("Neirasyta i db")

kam, tema, turinys = read_email_data(PATH_TO_EMAIL_TEMPLATE)
gmail_client.send_email(kam, tema, turinys)
logging.info(
    """
    Darbas atliktas:
    - Web puslapis nuskaitytas
    - Duomenys sukelti į duomenų bazę
    - El. laiškas išsiųstas
"""
)
