import json
import re
import sqlite3
import logging

from bs4 import BeautifulSoup
import google.generativeai as genai

MODEL = genai.GenerativeModel("gemini-1.5-flash-8b")


class Scraper:
    def __init__(self):
        pass

    def file_exist(self, response, file_name):
        if response.status_code == 200:
            logging.warning(
                f"failas {file_name} rastas. Status code: %d", response.status_code
            )
            return True
        else:
            logging.warning(
                f"failas {file_name} nerastas. Status code: %d", response.status_code
            )
            return False
            

    def extract_meta(self, url_soup):
        meta_description = url_soup.find("meta", attrs={"name": "description"})
        meta_keywords = url_soup.find("meta", attrs={"name": "keywords"})
        return (
            meta_description["content"] if meta_description else None,
            meta_keywords["content"] if meta_keywords else None,
        )

    def find_parent_that_doesnt_contain_h(self, tag, heading_tag):
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

        return self.find_parent_that_doesnt_contain_h(
            tag=parent, heading_tag=heading_tag
        )

    def extract_headings_and_content(self, html):
        soup = BeautifulSoup(markup=html, features="html.parser")

        headings = soup.find_all(["h1", "h2", "h3"])
        headings_and_content = []

        for heading in headings:
            container = self.find_parent_that_doesnt_contain_h(
                tag=heading, heading_tag=heading
            )
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


class LLM_Client:
    def __init__(self):
        pass

    def clean_json_string(self, json_string):
        pattern_opening = r"^(?:```json|json)\s*"

        pattern_closing = r"\s*```$"

        cleaned_string = re.sub(
            pattern_opening, "", json_string, flags=re.DOTALL | re.MULTILINE
        )

        cleaned_string = re.sub(
            pattern_closing, "", cleaned_string, flags=re.DOTALL | re.MULTILINE
        )

        return cleaned_string.strip()

    def clean_text_list(self, text, prompt):
        try:
            text_list = json.loads(text)
        except Exception:
            llm_response = MODEL.generate_content(prompt)
            cleaned_text = self.clean_json_string(llm_response.text)
            text_list = json.loads(cleaned_text)
        return text_list


def read_email_data(kelias):
    with open(kelias, "r") as dokumentas:
        eilutes = dokumentas.readlines()
        kam = eilutes[0].strip()
        tema = eilutes[1].strip()
        turinys = "".join(eilutes[2:]).strip()
    return kam, tema, turinys
