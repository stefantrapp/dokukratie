from urllib.parse import urljoin

from memorious.operations.parse import parse_for_metadata

from .base import BaseScraper
from .util import get_value_from_xp as x
from .util import re_first


class ParldokScraper(BaseScraper):
    def emit_search(self, data):
        """
        do a post request to the search overview page for given
        legislative_term and document_type to create a session that will be
        passed along to the next stages
        """
        res = self.context.http.post(
            self.base_url,
            data={
                "DokumententypId": data["document_type"],
                "LegislaturperiodenNummer": data["legislative_term"],
            },
        )
        self.context.log.info("Search [%s]: %s" % (res.status_code, res.url))
        self.context.emit(data={**data, **res.serialize()})

    def emit_parse_results(self, data):
        """
        parse the result list page and look for entries
        emit the detail urls for each entry and some metadata

        params in yaml config:
            optional:
                meta: dict for extracting metadata (key: xpath) that will
                      passed to the next stages
        """
        res = self.context.http.rehash(data)

        for item in res.html.xpath(self.context.params["item"]):
            url = x(item, self.context.params["detail_url"])
            if self.version < "5.6.5":
                url = re_first(r".*href='([\w\/\d]+)'.*", url)
            url = urljoin(self.base_url, url)

            if not self.context.skip_incremental(url):
                data["url"] = data["source_url"] = url
                parse_for_metadata(self.context, data, item)
                self.context.emit("fetch", data=data)
                if self.skip_while_testing("yield_items", 3):
                    break

    def emit_next_page(self, data):
        """
        look for "next page" links and emit the first one that is higher than
        the actual page
        """
        res = self.context.http.rehash(data)
        current_page = data.get("page", 1)

        for next_page_url in res.html.xpath(self.context.params["next_page"]):

            if self.version == "5.6.5":
                next_page_url = re_first(r".*href='([\w\/\d]+)'.*", next_page_url)

            next_page = int(next_page_url.split("/")[-1])
            if next_page > current_page:
                self.context.log.info("Next page: %s" % next_page)
                self.context.emit(
                    "next_page",
                    data={
                        **data,
                        **{
                            "url": urljoin(self.base_url, next_page_url),
                            "page": next_page,
                        },
                    },
                )
                return


# actual used stages for pipeline defined in yaml config


def init(context, data):
    scraper = ParldokScraper(context)
    scraper.emit_configuration()


def search(context, data):
    scraper = ParldokScraper(context)
    scraper.emit_search(data)


def parse_results(context, data):
    scraper = ParldokScraper(context)
    scraper.emit_parse_results(data)
    scraper.emit_next_page(data)
