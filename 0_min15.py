import requests
from bs4 import BeautifulSoup

# 1
min15_response = requests.get("https://15min.lt")

print(min15_response.status_code)
min15_html = min15_response.text

print("Kodas parsiųstas")

# 2
# min15_response = requests.get("https://15min.lt") kartojasi kintamasis
min15_soup = BeautifulSoup(min15_response.text, "html.parser")

min15_antrastes = min15_soup.find_all("h1")
for antraste in min15_antrastes:
   print("Antraste:", antraste.text.strip())

# 3
robots_txt = "https://www.15min.lt/robots.txt"  
min15_response = requests.get(robots_txt)

if min15_response.status_code == 200:
    print("failas robots.txt rastas")
else:
    print("failas robots.txt nerastas.")

#   4
# min15_response = requests.get("https://15min.lt") kartojasi kintamasis

# min15_soup = BeautifulSoup(min15_response.text, "html.parser") kartojasi kintamasis

description = None
keywords = None

results_description = min15_soup.find_all('meta') 
for meta in results_description:
    if meta.get ('name') == 'description':
        description = meta.get('content')
        print(description)
results_keywords = min15_soup.find_all('meta')
for meta in results_keywords:
    if meta.get ('name') == 'keywords':
        keywords = meta.get('content')
        print(keywords)
print(keywords)    

