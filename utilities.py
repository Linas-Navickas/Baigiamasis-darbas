import json
import re
import sqlite3
import logging
import os

from bs4 import BeautifulSoup
import google.generativeai as genai

model = genai.GenerativeModel("gemini-1.5-flash-8b")


def file_exist(response, file_name):
    if response.status_code == 200:
        logging.info(
            f"failas {file_name} rastas. Status code: %d", response.status_code
        )
        return True
    else:
        logging.warning(
            f"failas {file_name} nerastas. Status code: %d", response.status_code
        )
        return False


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


def clean_text_list(text, prompt):
    try:
        text_list = json.loads(text)
    except Exception:
        llm_response = model.generate_content(prompt)
        cleaned_text = clean_json_string(llm_response.text)
        # print(cleaned_text)
        # print("++++++++++++")
        text_list = json.loads(cleaned_text)
    return text_list


def execute_query(database, query):
    with sqlite3.connect(database) as conn:
        c = conn.cursor()
        c.execute(query)
        conn.commit()


insert_into_antrasciu_struktura_query = "INSERT INTO antrasciu_struktura (heading, your_suggestion) VALUES ('{heading}', '{suggestion}')"
insert_into_teksto_korekcijos = "INSERT INTO teksto_korekcijos_rekomendacijos (original_word, suggested_correction, reasoning) VALUES ('{original_word}', '{suggested_correction}', '{reasoning}')"


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
                    suggested_correction=text.get("suggested_correction", "").replace(
                        "'", ""
                    ),
                    reasoning=text.get("reasoning", "").replace("'", ""),
                )
            )


def read_email_data(kelias):
    with open(kelias, "r") as dokumentas:
        eilutes = dokumentas.readlines()
        kam = eilutes[0].strip()
        tema = eilutes[1].strip()
        turinys = "".join(eilutes[2:]).strip()
    return kam, tema, turinys
