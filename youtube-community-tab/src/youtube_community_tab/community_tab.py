import json
import re
from requests.utils import dict_from_cookiejar

from .helpers.utils import safely_get_value_from_key, get_auth_header, CLIENT_VERSION, search_key
from .requests_handler import requests_cache
from .post import Post


class CommunityTab(object):
    FORMAT_URLS = {
        "COMMUNITY_TAB": "https://www.youtube.com/{}/{}/posts",
        # HARD_CODED: This key seems to be constant to everyone, IDK
        "BROWSE_ENDPOINT": "https://www.youtube.com/youtubei/v1/browse?key=AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
    }

    REGEX = {
        "YT_INITIAL_DATA": "ytInitialData = ({(?:(?:.|\n)*)?});</script>",
        "COMMUNITY_TAB_URL": "^\/.*\/posts$"
    }

    def __init__(self, channel_name):
        self.channel_name = channel_name

        self.posts_continuation_token = None
        self.click_tracking_params = None
        self.visitor_data = None
        self.session_index = "0"
        self.posts = []
        self.community_url = None
        self.channel_id = None

    def load_posts(self, expire_after=0):
        headers = {
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": self.community_url
        }

        # Add authorization header
        current_cookies = dict_from_cookiejar(requests_cache.cookies)
        if "SAPISID" in current_cookies:
            headers["Authorization"] = get_auth_header(current_cookies["SAPISID"])

        if self.posts_continuation_token is None:
            try:
                # Get posts from community tab enpoint
                self.community_url = CommunityTab.FORMAT_URLS["COMMUNITY_TAB"].format("c", self.channel_name)
                r = requests_cache.get(self.community_url, expire_after=expire_after, headers=headers)
                if r.status_code != 200:
                    self.community_url = CommunityTab.FORMAT_URLS["COMMUNITY_TAB"].format("channel", self.channel_name)
                    r = requests_cache.get(self.community_url, expire_after=expire_after, headers=headers)

                if r.status_code != 200:
                    import sys

                    print(f"[Can't get data from the channel_name: {self.channel_name}]")
                    sys.exit()

                m = re.findall(CommunityTab.REGEX["YT_INITIAL_DATA"], r.text)
                data = json.loads(m[0])

                if self.channel_id is None:
                    self.channel_id = data["metadata"]["channelMetadataRenderer"]["externalId"]

            except IndexError as e:
                print("[Can't find yt_initial_data using the regex]")
                raise e
            except json.decoder.JSONDecodeError as e:
                print("[Can't parse yt_initial_data from the regex]")
                raise e
            except Exception as e:
                print("[Some non-expected exception, probably caused by requests...]")
                raise e

            tabs = data["contents"]["twoColumnBrowseResultsRenderer"]["tabs"]
            community_tab = CommunityTab.get_community_tab(tabs)
            community_tab_items = CommunityTab.get_items_from_community_tab(community_tab)

            self.click_tracking_params = CommunityTab.get_click_tracking_params_from_community_tab(community_tab)
            self.visitor_data = data["responseContext"]["webResponseContextExtensionData"]["ytConfigData"]["visitorData"]
            self.session_index = str(
                safely_get_value_from_key(data["responseContext"]["webResponseContextExtensionData"]["ytConfigData"], "sessionIndex", default="")
            )
            self.append_posts_from_items(community_tab_items)
        elif self.posts_continuation_token is not False:
            headers.update(
                {
                    "X-Goog-AuthUser": self.session_index,
                    "X-Origin": "https://www.youtube.com",
                    "X-Youtube-Client-Name": "1",
                    "X-Youtube-Client-Version": CLIENT_VERSION
                }
            )

            json_body = {
                "context": {
                    "client": {"clientName": "WEB", "clientVersion": CLIENT_VERSION, "originalUrl": self.community_url, "visitorData": self.visitor_data}
                },
                "continuation": self.posts_continuation_token,
                "clickTracking": {"clickTrackingParams": self.click_tracking_params}
            }

            r = requests_cache.post(CommunityTab.FORMAT_URLS["BROWSE_ENDPOINT"], json=json_body, expire_after=expire_after, headers=headers)

            data = r.json()
            append = data["onResponseReceivedEndpoints"][0]["appendContinuationItemsAction"]
            self.click_tracking_params = data["onResponseReceivedEndpoints"][0]["clickTrackingParams"]
            self.append_posts_from_items(safely_get_value_from_key(append, "continuationItems", default=[]))

    def append_posts_from_items(self, items):
        there_is_no_continuation_token = True
        for item in items:
            kind = list(item.keys())[0]

            if kind == "backstagePostThreadRenderer":
                post_data = item["backstagePostThreadRenderer"]["post"]
                self.posts.append(Post.from_data(post_data))
            elif kind == "continuationItemRenderer":
                self.posts_continuation_token = item[kind]["continuationEndpoint"]["continuationCommand"]["token"]
                there_is_no_continuation_token = False

        if there_is_no_continuation_token:
            self.posts_continuation_token = False

    @staticmethod
    def get_community_tab(tabs):
        for tab in tabs:
            if "tabRenderer" in tab and re.match(CommunityTab.REGEX["COMMUNITY_TAB_URL"], tab["tabRenderer"]["endpoint"]["commandMetadata"]["webCommandMetadata"]["url"]):
                return tab
        raise Exception(f"[Could not find a Community tab in the channel response]")

    @staticmethod
    def get_items_from_community_tab(tab):
        try:
            return tab["tabRenderer"]["content"]["sectionListRenderer"]["contents"][0]["itemSectionRenderer"]["contents"]
        except Exception as e:
            print("[Can't get the contents from the tab]")
            raise e

    @staticmethod
    def get_click_tracking_params_from_community_tab(tab):
        try:
            return tab["tabRenderer"]["content"]["sectionListRenderer"]["trackingParams"]
        except Exception as e:
            print("[Can't get tracking params from the tab")
            raise e
