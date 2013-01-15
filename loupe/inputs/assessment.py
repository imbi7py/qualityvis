import wapiti
import re
from base import Input


def find_tmpl(text):
    ratings = re.findall(r'\|\s*((class|currentstatus)\s*=\s*(.+?))(\b|\|)', text, re.I)
    if not ratings:
        return None
    else:
        return [rating[2] for rating in ratings]


class Assessment(Input):
    prefix = 'a'
    def fetch(self):
        return wapiti.get_talk_page(self.page_title)

    stats = {
        'assessment': lambda f_res: find_tmpl(f_res),
    }
