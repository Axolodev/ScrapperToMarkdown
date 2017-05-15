from scrapy.linkextractors import LinkExtractor
from scrapy.crawler import CrawlerProcess, CrawlerRunner
from twisted.internet import defer, reactor
from bs4 import BeautifulSoup
from shutil import copyfile
import logging
import sys
import re
import scrapy
import os
import json

# Filesystem: https://learnpythonthehardway.org/book/ex16.html
#

logging.getLogger('scrapy').propagate = False
pages = []
activity_urls = []

# Scrapea la pagina principal. Obtiene todos los URLs de todas las actividades.
class MainSpider(scrapy.Spider):
    name = "Main_Spider"
    start_urls = ["http://127.0.0.1:8080/"]

    def parse(self, response):
        global activity_urls
        # Obtener todos los links
        links = response.xpath("//body//a/@href").extract()
        for link in links:
            # Verificar si el link que se obtuvo es una actividad. La pagina
            # principal tiene muchos links, por lo que es necesario filtrarlos
            result = re.match(r"MP?(\d+\.\d+(\.\d+)?)\.html?", link)
            if result is not None:
                activity_urls.append("http://127.0.0.1:8080/" + link)

class ActivitySpider(scrapy.Spider):
    name = 'ActivitySpider'

    def __init__(self, urls):
        self.start_urls = urls

    def parse(self, response):
        global activity_urls
        global pages
        # La pagina tendra estructura de diccionario
        page = {}
        print("Scraping url:", response.url)
        page["doc_name"] = response.url.replace("http://127.0.0.1:8080/", "")
        # Sacar el body del html
        page_body = response.xpath("//body").extract_first()
        try:
            # Hacer que BeautifulSoup parsee el html del body
            soup = BeautifulSoup(page_body)
            # Quitar los scripts del texto
            soup.body.script.decompose()
            # Obtener texto limpio
            page["html"] = soup.get_text()
            # Obtener titulo
            page["title"] = response.xpath("//title").extract_first().encode("utf-8")
            # Obtener imagenes
            page["images"] = response.xpath("//img/@src").extract()
        except Exception as e:
            print(e)
        pages.append(page)

runner = CrawlerRunner()

# El Scraping de las paginas se ejecuta en dos etapas:
# 1. Scraping de la pagina principal, obtiene todos los URLs de las actividades
#    a las que se les hara scraping en la segunda etapa.
# 2. Scraping de las actividades. Obtiene el contenido especifico de cada
#    actividad individual, esto es: imagenes y texto de la pagina.
# Este proceso genera una lista de paginas de cada una de las actividades, la
# cual se procesa mas abajo.
# Para poder hacer scraping en dos procesos separados, se utilizan
# inlineCallbacks. Para leer mas sobre esto, visitar el siguiente link:
# https://hackedbellini.org/development/writing-asynchronous-python-code-with-twisted-using-inlinecallbacks/
@defer.inlineCallbacks
def crawl():
    yield runner.crawl(MainSpider)
    yield runner.crawl(ActivitySpider, activity_urls)
    reactor.stop()

crawl()
reactor.run()

modules = {}
constant_pug_content = """
extends ../templates/activity_template.pug
prepend title
    | {0}

block activity_content
    .mdl-grid
        .mdl-layout-spacer
            include:markdown-it {1}"""


json_output = []

print("Done. Starting doc gen")
for page in pages:
    global modules
    global constant_pug_content
    print("Processing " + page["doc_name"])

    page_json = {}
    # Carpeta donde se guardaran los archivos
    root_folder = "pug_files/"
    # Nombre del archivo que se trabajara en esta iteracion
    filename = page["doc_name"].replace(".html", "").replace(".htm", "")
    # Carpeta donde se guardaran los resultados de esta iteracion
    content_output_path = root_folder + "content/" + filename + "/"


    if not os.path.exists(content_output_path):
        os.makedirs(content_output_path)
    # Archivo de salida del codigo pug
    pug_file = open(root_folder + filename + ".pug", "w+");
    # Archivo de salida de texto en formato markdown
    markdown_file = open(content_output_path + filename + ".md", "w+")

    # Limpiar el texto un poco mas
    try:
        page["html"] = re.sub(r"\r|\t", "", page["html"])
        page["html"] = re.sub(r"[ ]+", " ", page["html"])
        # Codificar el html a un formato procesable por python antes de imprimirlo
        page["html"] = page["html"].encode("utf-8")

        markdown_file.write(page["html"])
    except Exception as e:
        print("ERROR " + page["doc_name"])
        print(page)
        continue

    # Revisar si la pagina tiene imagenes
    if page.get("images", None) is not None:
        for image in page["images"]:
            # Copiar las imagenes
            image = image.encode("utf-8")
            markdown_file.write("[![](" + content_output_path + image + ")]\n")
            try:
                copyfile("/home/robruizr/Documents/moondoreyes.com/public_html/" + image, content_output_path + image)
            except Exception as e:
                pass


    pug_content = constant_pug_content.format(page.get("title", page["doc_name"]), content_output_path + filename + ".md")

    pug_file.write(pug_content)

    module_number = re.findall(r'\d+', filename)[0]
    module_exists = modules.get(module_number) is not None

    module = {}

    if module_exists:
        module = modules.get(module_number)
    else:
        module = {
                "color":"",
                "topics": []
                }

    topics = module["topics"]
    topics.append({"file" : filename, "name":"", "image" : "", "description": ""})
    module["topics"] = topics

    modules[module_number] = module


print("Modules:")
for module_number, topics in modules.iteritems():
    print(module_number)
    print(topics)

with open("modules.json", "w") as outfile:
    json.dump(modules, outfile)
