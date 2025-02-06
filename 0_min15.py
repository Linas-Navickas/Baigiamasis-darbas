from bs4 import BeautifulSoup
import requests
import os
import google.generativeai as genai
from dotenv import load_dotenv
import json 
import re
import sqlite3

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

robots_txt = "https://www.15min.lt/robots.txt"  
min15_response = requests.get(robots_txt)

if min15_response.status_code == 200:
    print("failas robots.txt rastas")
else:
    print("failas robots.txt nerastas.")
   

def extract_meta(min15_soup):
    meta_description = min15_soup.find("meta", attrs={"name": "description"})
    meta_keywords = min15_soup.find("meta", attrs={"name": "keywords"})
    return (
        meta_description["content"] if meta_description else None,
        meta_keywords["content"] if meta_keywords else None,)

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

min15_response = requests.get("https://15min.lt")

min15_soup = BeautifulSoup(min15_response.text, "html.parser")

min15_antrastes = min15_soup.find_all("h1")
description, keywords = extract_meta(min15_soup)
informacija = extract_headings_and_content(min15_response.text)
response_1 = model.generate_content(PROMPT_SEO.format(text=informacija))

min15_text = min15_soup.get_text()

clean_text = " ".join(min15_text.split())


response_2 = model.generate_content(PROMPT_WORD.format(text=clean_text))

heading_text = clean_json_string(response_1.text)
try:
    heading_text_list = json.loads(heading_text)
except Exception:
    response_1 = model.generate_content(PROMPT.format(text=informacija)) 
    heading_text = clean_json_string(response_1.text)
    heading_text_list = json.loads(heading_text)


corection_text = clean_json_string(response_2.text)
try:
    corection_text_list = json.loads(corection_text)
except Exception:
    response_2 = model.generate_content(PROMPT.format(text=clean_text))
    corection_text = clean_json_string(response_2.text)
    corection_text_list = json.loads(corection_text)


with sqlite3.connect("heading_database.db") as conn: 
    c = conn.cursor()
    c.execute(
        "CREATE TABLE IF NOT EXISTS antrasciu_struktura (heading text, your_suggestion text)"
    )

with sqlite3.connect("heading_database.db") as conn:
    c = conn.cursor()
    for text in heading_text_list:
        c.execute(f"INSERT INTO antrasciu_struktura VALUES ('{text["heading"].replace("'","")}', '{text["your_suggestion"].replace("'","")}')")


with sqlite3.connect("webpage_database.db") as conn: 
    c = conn.cursor()
    c.execute(
        "CREATE TABLE IF NOT EXISTS teksto_korekcijos_rekomendacijos (original_word text, suggested_correction text, reasoning text)"
    )

with sqlite3.connect("webpage_database.db") as conn:
    c = conn.cursor()
    for text in corection_text_list:
        try:    
            c.execute(f"INSERT INTO teksto_korekcijos_rekomendacijos VALUES ('{text["original_word"].replace("'","")}', '{text["suggested_correction"].replace("'","")}', '{text["reasoning"].replace("'","")}')")
        except Exception:
            print('KLAIDA')
            print(text)

