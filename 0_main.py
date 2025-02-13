import os
import logging

from bs4 import BeautifulSoup
import requests
import google.generativeai as genai
from dotenv import load_dotenv

from gmail_client import GmailClient
from utilities import (
    file_exist,
    extract_meta,
    extract_headings_and_content,
    clean_text_list,
    execute_query,
    add_data,
    read_email_data,
)

load_dotenv("./API_raktas.env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
MODEL = genai.GenerativeModel("gemini-1.5-flash-8b")

URL = "https://15min.lt/" # padaryti kintamuosius didziosioms raidem
ROBOTS_TXT = URL + "robots.txt"
PATH_TO_EMAIL_TEMPLATE = "./mail_duomenys.txt"

gmail_client = GmailClient()

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

antrasciu_struktura_create_query = """
            CREATE TABLE IF NOT EXISTS antrasciu_struktura (
                heading TEXT,
                your_suggestion TEXT
            )
        """
teksto_korekcijos_rekomendacijos_create_query = """
                CREATE TABLE IF NOT EXISTS teksto_korekcijos_rekomendacijos (
                    original_word TEXT,
                    suggested_correction TEXT,
                    reasoning TEXT
                )
            """

execute_query("heading_database.db", antrasciu_struktura_create_query)
execute_query("webpage_database.db", teksto_korekcijos_rekomendacijos_create_query)

url_response_robots = requests.get(ROBOTS_TXT)
file_exist(response=url_response_robots, file_name="robots.txt")

url_response = requests.get(URL)
url_soup = BeautifulSoup(url_response.text, "html.parser")

url_antrastes = url_soup.find_all("h1")
description, keywords = extract_meta(url_soup)
get_headings_info = extract_headings_and_content(url_response.text)

seo_llm_response = MODEL.generate_content(PROMPT_SEO.format(text=get_headings_info))
heading_text_list = clean_text_list(
    text=seo_llm_response.text, prompt=(PROMPT_SEO.format(text=get_headings_info))
)

url_text = url_soup.get_text()

clean_text = " ".join(url_text.split())

word_llm_response = MODEL.generate_content(PROMPT_WORD.format(text=clean_text))
corection_text_list = clean_text_list(
    text=word_llm_response.text, prompt=(PROMPT_WORD.format(text=clean_text))
)

if corection_text_list and heading_text_list:
    add_data(
        heading_text_list=heading_text_list, corection_text_list=corection_text_list
    )
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
