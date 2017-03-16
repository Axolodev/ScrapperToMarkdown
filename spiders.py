
import scrapy
import logging
import re


logging.getLogger('scrapy').propagate = False

class MainSpider(scrapy.Spider):
    name = "Main_Spider"
    allowed_domains = ["http://www.moondoreyes.com/"]
    start_urls = ["http://www.moondoreyes.com/"]

    def parse(self, response):
        links = response.xpath("//body//a/@href").extract()
        for link in links:
            result = re.match(r"MP?(\d+\.\d+(\.\d+)?)\.html?", link)
            if result is not None:
                print(link)
