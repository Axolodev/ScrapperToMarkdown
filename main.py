from scrapy.linkextractors import LinkExtractor
from scrapy.crawler import CrawlerProcess, CrawlerRunner
from twisted.internet import defer, reactor
from collections import OrderedDict
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

json_output = []

print("Done. Starting doc gen")
for page in pages:
    global modules
    print("Processing " + page["doc_name"])

    page_json = {}
    # Carpeta donde se guardaran los archivos
    root_folder = "./"
    # Nombre del archivo que se trabajara en esta iteracion
    filename = page["doc_name"].replace(".html", "").replace(".htm", "")
    # Identificador del modulo al que pertenece el archivo de esta iteracion
    module_id = re.findall(r'P?\d+', filename)[0]
    # Carpeta donde se guardaran los resultados de esta iteracion
    content_output_path = root_folder + "content/" + module_id + "/" + filename + "/"

    if not os.path.exists(content_output_path):
        os.makedirs(content_output_path)
    # Archivo de salida de texto en formato markdown
    markdown_file = open(content_output_path + filename + ".md", "w+")

    # Limpiar el texto un poco mas
    try:
        page["html"] = re.sub(r"\r|\t", "", page["html"])
        page["html"] = re.sub(r"[ ]+", " ", page["html"])
        # Codificar el html a un formato procesable por python antes de imprimirlo
        page["html"] = page["html"].encode("utf-8")

        # Imprimir al archivo
        markdown_file.write(page["html"])
    except Exception as e:
        print("ERROR " + page["doc_name"])
        print(page)
        continue

    markdown_file.write("<div class=\"mdl-grid\">\n")
    # Revisar si la pagina tiene imagenes
    if page.get("images", None) is not None:
        for image in page["images"]:
            # Copiar las imagenes
            image = image.encode("utf-8")
            new_image_name = image.replace(" ", "_")
            markdown_file.write("<div class=\"mdl-cell mdl-cell--6-col mdl-typography--text-center\">\n<img src='" + content_output_path + new_image_name + "'>\n</div>\n")
            try:
                copyfile("/home/robruizr/Documents/moondoreyes.com/public_html/" + image, content_output_path + new_image_name)
            except Exception as e:
                pass

    markdown_file.write("</div>")

    module_exists = modules.get(module_id) is not None

    module = {}

    if module_exists:
        module = modules.get(module_id)
    else:
        module = {
                "color": "",
                "name" : "",
                "topics": []
            }

    topics = module["topics"]
    topics.append({"file" : filename, "name":"", "image" : "", "description": ""})
    module["topics"] = topics

    modules[module_id] = module

modules = OrderedDict(sorted(modules.items(), key = lambda e: -10 + int(re.findall(r'\d+', e[0])[0]) if e[0].startswith("P") else int(e[0])))

print("Modules:")
for module_id, topics in modules.iteritems():
    print(module_id)
    print(topics)

with open("modules.json", "w") as outfile:
    json.dump(modules, outfile)
