from scrapy.linkextractors import LinkExtractor
from scrapy.crawler import CrawlerProcess, CrawlerRunner
from twisted.internet import defer, reactor
from bs4 import BeautifulSoup
import logging
import sys
import re
import scrapy

# Filesystem: https://learnpythonthehardway.org/book/ex16.html
#

logging.getLogger('scrapy').propagate = False
pages = []
activity_urls = []

class MainSpider(scrapy.Spider):
    name = "Main_Spider"
    start_urls = ["http://127.0.0.1:8080/"]

    def parse(self, response):
        global activity_urls
        links = response.xpath("//body//a/@href").extract()
        for link in links:
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
        page = {}
        print("Scrapping url:", response.url)
        page["doc_name"] = response.url.replace("http://127.0.0.1:8080/", "")
        page_body = response.xpath("//body").extract_first()
        try:
            soup = BeautifulSoup(page_body)
            soup.body.script.decompose()
            page["html"] = soup.get_text()
            page["images"] = response.xpath("//img/@src").extract()
        except Exception as e:
            print(e)
        pages.append(page)

runner = CrawlerRunner()

@defer.inlineCallbacks # https://hackedbellini.org/development/writing-asynchronous-python-code-with-twisted-using-inlinecallbacks/
def crawl():
    yield runner.crawl(MainSpider)
    yield runner.crawl(ActivitySpider, activity_urls)
    reactor.stop()

crawl()
reactor.run()

print("Done. Starting doc-gen")
for page in pages:
    page["html"] = re.sub(r"\r|\xa0|\t", "", page["html"])
    page["html"] = re.sub(r"[ ]+", " ", page["html"])
    # page["html"] = page["html"].replace("\n", "").replace("\r", "")
    print(page)
    sys.exit()
