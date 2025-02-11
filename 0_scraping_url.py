from bs4 import BeautifulSoup
import requests
import os
import google.generativeai as genai
from dotenv import load_dotenv
import json
import re
import sqlite3
from gmail_client import GmailClient

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
load_dotenv("./API_raktas.env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash-8b")


def extract_meta(url_soup):
    meta_description = url_soup.find("meta", attrs={"name": "description"})
    meta_keywords = url_soup.find("meta", attrs={"name": "keywords"})
    return (
        meta_description["content"] if meta_description else None,
        meta_keywords["content"] if meta_keywords else None,
    )


def find_parent_that_doesnt_contain_h(tag, heading_tag):
    parent = tag.parent

    has_another_h_tag = False
    if parent is None:
        return tag

    all_parent_elements = parent.find_all()
    for element in all_parent_elements:
        if element.name.startswith("h") and element != heading_tag:
            has_another_h_tag = True

    if has_another_h_tag:
        return tag

    return find_parent_that_doesnt_contain_h(tag=parent, heading_tag=heading_tag)


def extract_headings_and_content(html):
    soup = BeautifulSoup(markup=html, features="html.parser")

    headings = soup.find_all(["h1", "h2", "h3"])
    headings_and_content = []

    for heading in headings:
        container = find_parent_that_doesnt_contain_h(tag=heading, heading_tag=heading)
        elements_text = [
            el.get_text(" ", strip=True)
            for el in container
            if el.get_text(" ", strip=True) and el != heading
        ]

        heading_text = heading.get_text(" ", strip=True)
        siblings_text = " ".join(elements_text)
        if heading_text != siblings_text:
            headings_and_content.append(
                {
                    "heading": heading_text,
                    "text": siblings_text,
                }
            )

    text = ""
    for el in headings_and_content:
        for key, value in el.items():
            text += f"{key}: {value}\n"

    return text


def clean_json_string(json_string):
    pattern_opening = r"^(?:```json|json)\s*"

    pattern_closing = r"\s*```$"

    cleaned_string = re.sub(
        pattern_opening, "", json_string, flags=re.DOTALL | re.MULTILINE
    )

    cleaned_string = re.sub(
        pattern_closing, "", cleaned_string, flags=re.DOTALL | re.MULTILINE
    )

    return cleaned_string.strip()


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
insert_into_antrasciu_struktura_query = "INSERT INTO antrasciu_struktura (heading, your_suggestion) VALUES ('{heading}', '{suggestion}')"
insert_into_teksto_korekcijos = "INSERT INTO teksto_korekcijos_rekomendacijos (original_word, suggested_correction, reasoning) VALUES ('{original_word}', '{suggested_correction}', '{reasoning}')"


def execute_query(database, query):
    with sqlite3.connect(database) as conn:
        c = conn.cursor()
        c.execute(query)
        conn.commit()


execute_query("heading_database.db", antrasciu_struktura_create_query)
execute_query("webpage_database.db", teksto_korekcijos_rekomendacijos_create_query)


def add_data(heading_text_list, corection_text_list):
    with sqlite3.connect("heading_database.db") as conn:
        c = conn.cursor()
        for text in heading_text_list:
            c.execute(
                insert_into_antrasciu_struktura_query.format(
                    heading=text["heading"], suggestion=text["your_suggestion"]
                )
            )

    with sqlite3.connect("webpage_database.db") as conn:
        c = conn.cursor()
        for text in corection_text_list:
            c.execute(
                insert_into_teksto_korekcijos.format(
                    original_word=text.get("original_word", "").replace("'", ""),
                    suggested_correction=text.get("suggested_correction", "").replace("'", ""),
                    reasoning=text.get("reasoning", "").replace("'", ""),
                )
            )

def skaityti_laisko_duomenis(kelias):
    with open(kelias, 'r') as dokumentas:
        eilutes = dokumentas.readlines()
        kam = eilutes[0].strip()
        tema = eilutes[1].strip()
        turinys = "".join(eilutes[2:]).strip()
    return kam, tema, turinys

url = "https://15min.lt/"
robots_txt = url + "robots.txt"
url_response_robots = requests.get(robots_txt)

if url_response_robots.status_code == 200:
    print("failas robots.txt rastas")
else:
    print("failas robots.txt nerastas.")

url_response = requests.get(url)

url_soup = BeautifulSoup(url_response.text, "html.parser")

url_antrastes = url_soup.find_all("h1")
description, keywords = extract_meta(url_soup)
informacija = extract_headings_and_content(url_response.text)
response_1 = model.generate_content(PROMPT_SEO.format(text=informacija))

url_text = url_soup.get_text()

clean_text = " ".join(url_text.split())


response_2 = model.generate_content(PROMPT_WORD.format(text=clean_text))

heading_text = clean_json_string(response_1.text)
try:
    heading_text_list = json.loads(heading_text)
except Exception:
    response_1 = model.generate_content(PROMPT_SEO.format(text=informacija))
    heading_text = clean_json_string(response_1.text)
    heading_text_list = json.loads(heading_text)


corection_text = clean_json_string(response_2.text)
try:
    corection_text_list = json.loads(corection_text)
except Exception:
    response_2 = model.generate_content(PROMPT_WORD.format(text=clean_text))
    corection_text = clean_json_string(response_2.text)
    corection_text_list = json.loads(corection_text)

if corection_text:
    add_data(heading_text_list=heading_text_list, corection_text_list=corection_text_list)
else:
    print("Neirasyta i db") 

gmail_client = GmailClient()

kelias = "./mail_duomenys.txt"

kam, tema, turinys = skaityti_laisko_duomenis(kelias) 
gmail_client.send_email(kam, tema, turinys)   
print("""Darbas atliktas:
      web puslapis nuskaitytas
      duomenys sukelti i duomenu baze
      el. laiskas isiustas      
      """)