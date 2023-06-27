import json
import re
from requests.utils import dict_from_cookiejar
from base64 import urlsafe_b64encode

from .helpers.clean_items import clean_content_text, clean_backstage_attachment
from .helpers.utils import safely_get_value_from_key, search_key, get_auth_header, CLIENT_VERSION
from .requests_handler import requests_cache
from .comment import Comment


class Post(object):
    FORMAT_URLS = {
        "POST": "https://www.youtube.com/post/{}",
        # HARD_CODED: This key seems to be constant to everyone, IDK
        "BROWSE_ENDPOINT": "https://www.youtube.com/youtubei/v1/browse?key=AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8",
        "CREATE_COMMENT_ENDPOINT": "https://www.youtube.com/youtubei/v1/comment/create_comment?key=AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8&prettyPrint=false"
    }

    REGEX = {
        "YT_INITIAL_DATA": "ytInitialData = ({(?:(?:.|\n)*)?});</script>"
    }

    def __init__(self, post_id, channel_id, author=None, content_text=None, backstage_attachment=None, vote_count=None, sponsor_only_badge=None, published_time_text=None, original_post=None):
        self.post_id = post_id
        self.channel_id = channel_id
        self.author = author
        self.content_text = content_text
        self.backstage_attachment = backstage_attachment
        self.vote_count = vote_count
        self.sponsor_only_badge = sponsor_only_badge
        self.published_time_text = published_time_text
        self.original_post = original_post

        self.first = True
        self.comments = []
        self.comments_continuation_token = None
        self.click_tracking_params = None
        self.visitor_data = None
        self.session_index = "0"

    def as_json(self):
        return {
            "post_id": self.post_id,
            "channel_id": self.channel_id,
            "author": self.author,
            "content_text": self.content_text,
            "backstage_attachment": self.backstage_attachment,
            "vote_count": self.vote_count,
            "sponsor_only_badge": self.sponsor_only_badge,
            "original_post": self.original_post and self.original_post.as_json()
        }

    def get_published_string(self):
        return self.published_time_text

    @staticmethod
    def from_post_id(post_id, expire_after=0):
        headers = {
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": Post.FORMAT_URLS["POST"].format(post_id)
        }

        # Add authorization header
        current_cookies = dict_from_cookiejar(requests_cache.cookies)
        if "SAPISID" in current_cookies:
            headers["Authorization"] = get_auth_header(current_cookies["SAPISID"])

        post_url = Post.FORMAT_URLS["POST"].format(post_id)
        r = requests_cache.get(post_url, expire_after=expire_after, headers=headers)

        m = re.findall(Post.REGEX["YT_INITIAL_DATA"], r.text)
        data = json.loads(m[0])
        community_tab = data["contents"]["twoColumnBrowseResultsRenderer"]["tabs"][0]
        community_tab_items = Post.get_items_from_community_tab(community_tab)

        post_data = community_tab_items[0]["backstagePostThreadRenderer"]["post"]

        post = Post.from_data(post_data)
        post.get_first_continuation_token(data)
        post.get_click_tracking_params(data)
        post.visitor_data = data["responseContext"]["webResponseContextExtensionData"]["ytConfigData"]["visitorData"]
        post.session_index = str(
            safely_get_value_from_key(data, "responseContext", "webResponseContextExtensionData", "ytConfigData", "sessionIndex", default="")
        )

        return post

    def __str__(self):
        return json.dumps(self.as_json(), indent=4)

    def __repr__(self):
        return self.__str__()

    def get_thumbnails(self):
        # Returns a list of the thumbnails in different resolutions of
        # all images present in the post
        thumbnails = []

        if self.backstage_attachment is not None:
            renderer_key = list(self.backstage_attachment.keys())[0]

            if renderer_key == "videoRenderer":
                thumbnails = [self.backstage_attachment[renderer_key]["thumbnail"]["thumbnails"]]
            elif renderer_key == "backstageImageRenderer":
                thumbnails = [self.backstage_attachment[renderer_key]["image"]["thumbnails"]]
            elif renderer_key == "postMultiImageRenderer":
                thumbnails = [img["backstageImageRenderer"]["image"]["thumbnails"] for img in self.backstage_attachment[renderer_key]["images"]]
            elif renderer_key == "pollRenderer":
                print("[There is nothing implemented for polls]")
                thumbnails = []
            else:
                raise Exception("There is no implementation for renderer_key={renderer_key} yet")

        return thumbnails

    def get_first_continuation_token(self, data):
        self.comments_continuation_token = data["contents"]["twoColumnBrowseResultsRenderer"]["tabs"][0]["tabRenderer"]["content"]["sectionListRenderer"][
            "contents"][1]["itemSectionRenderer"]["contents"][0]["continuationItemRenderer"]["continuationEndpoint"]["continuationCommand"]["token"]

    def get_click_tracking_params(self, data):
        self.click_tracking_params = data["contents"]["twoColumnBrowseResultsRenderer"]["tabs"][0]["tabRenderer"]["content"]["sectionListRenderer"][
            "contents"][1]["itemSectionRenderer"]["contents"][0]["continuationItemRenderer"]["continuationEndpoint"]["clickTrackingParams"]

    def get_click_tracking_params(self, data):
        self.click_tracking_params = data["contents"]["twoColumnBrowseResultsRenderer"]["tabs"][0]["tabRenderer"]["content"]["sectionListRenderer"]["contents"][
            1
        ]["itemSectionRenderer"]["contents"][0]["continuationItemRenderer"]["continuationEndpoint"]["clickTrackingParams"]

    def load_comments(self, expire_after=0):
        headers = {
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": Post.FORMAT_URLS["POST"].format(self.post_id)
        }

        # Add authorization header
        current_cookies = dict_from_cookiejar(requests_cache.cookies)
        if "SAPISID" in current_cookies:
            headers["Authorization"] = get_auth_header(current_cookies["SAPISID"])

        if self.comments_continuation_token is None:
            try:
                r = requests_cache.get(Post.FORMAT_URLS["POST"].format(self.post_id), expire_after=expire_after, headers=headers)

                m = re.findall(Post.REGEX["YT_INITIAL_DATA"], r.text)
                data = json.loads(m[0])

                self.get_first_continuation_token(data)
                self.get_click_tracking_params(data)
                self.visitor_data = data["responseContext"]["webResponseContextExtensionData"]["ytConfigData"]["visitorData"]
                self.session_index = str(data["responseContext"]["webResponseContextExtensionData"]["ytConfigData"]["sessionIndex"])
                self.load_comments(expire_after=expire_after)
            except Exception as e:
                print("[Some non-expected exception, probably caused by requests...]")
                raise e
        elif self.comments_continuation_token is not False:
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
                    "client": {
                        "clientName": "WEB",
                        "clientVersion": CLIENT_VERSION,
                        "originalUrl": Post.FORMAT_URLS["POST"].format(self.post_id),
                        "visitorData": self.visitor_data
                    }
                },
                "continuation": self.comments_continuation_token,
                "clickTracking": {"clickTrackingParams": self.click_tracking_params}
            }

            r = requests_cache.post(Post.FORMAT_URLS["BROWSE_ENDPOINT"], json=json_body, expire_after=expire_after, headers=headers)

            data = r.json()
            if self.first:
                if "continuationItems" not in data["onResponseReceivedEndpoints"][1]["reloadContinuationItemsCommand"]:
                    # There are no comments
                    continuation_items = []
                else:
                    append = data["onResponseReceivedEndpoints"][1]["reloadContinuationItemsCommand"]
                    continuation_items = safely_get_value_from_key(append, "continuationItems", default=[])
                    self.first = False
            else:
                append = data["onResponseReceivedEndpoints"][0]["appendContinuationItemsAction"]
                continuation_items = safely_get_value_from_key(append, "continuationItems", default=[])

            self.click_tracking_params = data["trackingParams"]
            self.append_comments_from_items(continuation_items)

    def append_comments_from_items(self, items):
        there_is_no_continuation_token = True
        for item in items:
            kind = list(item.keys())[0]

            if kind == "commentThreadRenderer":
                self.comments.append(
                    Comment.from_data(
                        item[kind]["comment"]["commentRenderer"],
                        self.post_id,
                        self.channel_id,
                        safely_get_value_from_key(
                            item[kind],
                            "replies",
                            "commentRepliesRenderer",
                            "contents",
                            0,
                            "continuationItemRenderer",
                            "continuationEndpoint",
                            "continuationCommand",
                            "token"
                        ),
                        safely_get_value_from_key(
                            item[kind],
                            "replies",
                            "commentRepliesRenderer",
                            "contents",
                            0,
                            "continuationItemRenderer",
                            "continuationEndpoint",
                            "clickTrackingParams"
                        ),
                        self.visitor_data,
                        self.session_index
                    )
                )
            elif kind == "continuationItemRenderer":
                self.comments_continuation_token = item[kind]["continuationEndpoint"]["continuationCommand"]["token"]
                there_is_no_continuation_token = False

        if there_is_no_continuation_token:
            self.comments_continuation_token = False

    def get_text(self):
        runs = safely_get_value_from_key(self.content_text, "runs", default=[])

        if self.content_text is not None:
            return "\n".join([run["text"] for run in runs])
        return None

    def get_create_comment_params(self):
        if self.channel_id is None or self.post_id is None:
            return None

        params = [
            b"*\x02\b\x00P\x01\xA2\x01",
            len(self.post_id).to_bytes(1, "big"),
            self.post_id.encode(),
            b"\xAA\x01",
            len(self.channel_id).to_bytes(1, "big"),
            self.channel_id.encode(),
        ]

        params = urlsafe_b64encode(b"".join(params)).decode().replace("=", "%3D")

        return params

    def create_comment(self, comment_text):
        headers = {
            "Accept-Language": "en-US,en;q=0.9",
            "x-origin": "https://www.youtube.com"
        }

        current_cookies = dict_from_cookiejar(requests_cache.cookies)
        if "SAPISID" in current_cookies:
            headers["Authorization"] = get_auth_header(current_cookies["SAPISID"])

        json_body = {
            "context": {
                "client": {
                    "clientName": "WEB",
                    "clientVersion": CLIENT_VERSION,
                },
            },
            "createCommentParams": self.get_create_comment_params(),
            "commentText": comment_text
        }

        r = requests_cache.post(
            Post.FORMAT_URLS["CREATE_COMMENT_ENDPOINT"],
            json=json_body,
            headers=headers
        )

        try:
            data = r.json()
            comment_id = search_key("comment", data)[0][1]["commentRenderer"]["commentId"]

            return Comment.from_ids(comment_id, self.post_id, self.channel_id)
        except Exception as e:
            raise e

    @staticmethod
    def from_data(post_data):
        if "sharedPostRenderer" in post_data:
            data = post_data["sharedPostRenderer"]
            data["contentText"] = data.pop("content")
            data["authorText"] = data.pop("displayName")
            data["authorEndpoint"] = data.pop("endpoint")

            original_post_data = post_data["sharedPostRenderer"]["originalPost"]
            data["originalPost"] = Post.from_data(original_post_data)

        elif "backstagePostRenderer" in post_data:
            data = post_data["backstagePostRenderer"]
        else:
            raise NotImplementedError(f"[post_kind={list(post_data.keys())[0]} is not implemented yet!]")

        data["channelId"] = data["authorEndpoint"]["browseEndpoint"]["browseId"]

        # clean the author cause it's different here for some reason
        for item in data["authorText"]["runs"]:
            item["browseEndpoint"] = item["navigationEndpoint"]["browseEndpoint"]
            item["browseEndpoint"]["url"] = item["navigationEndpoint"]["commandMetadata"]["webCommandMetadata"]["url"]
            item.pop("navigationEndpoint")
        data["authorEndpoint"]["browseId"] = data["authorEndpoint"]["browseEndpoint"]["browseId"]
        author_url = data["authorEndpoint"]["commandMetadata"]["webCommandMetadata"]["url"]
        data["authorEndpoint"]["url"] = author_url
        for value in ["clickTrackingParams", "commandMetadata", "browseEndpoint"]:
            data["authorEndpoint"].pop(value)

        post = Post(
            data["postId"],
            channel_id=data["channelId"],
            author={
                "authorText": safely_get_value_from_key(data, "authorText"),
                "authorThumbnail": safely_get_value_from_key(data, "authorThumbnail"),
                "authorEndpoint": safely_get_value_from_key(data, "authorEndpoint")
            },
            content_text=clean_content_text(safely_get_value_from_key(data, "contentText")),
            backstage_attachment=clean_backstage_attachment(safely_get_value_from_key(data, "backstageAttachment", default=None)),
            vote_count=safely_get_value_from_key(data, "voteCount"),
            sponsor_only_badge=safely_get_value_from_key(data, "sponsorsOnlyBadge", default=None),
            published_time_text=safely_get_value_from_key(data, "publishedTimeText", "runs", 0, "text", default=None),
            original_post=safely_get_value_from_key(data, "originalPost", default=None)
        )

        post.raw_data = data

        return post

    @staticmethod
    def get_items_from_community_tab(tab):
        try:
            return tab["tabRenderer"]["content"]["sectionListRenderer"]["contents"][0]["itemSectionRenderer"]["contents"]
        except Exception as e:
            print("[Can't get the contents from the tab]")
            raise e
