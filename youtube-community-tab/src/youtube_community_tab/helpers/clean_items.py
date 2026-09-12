from urllib.parse import parse_qs, unquote, urlparse
from .utils import safely_get_value_from_key as safe
from .utils import safely_pop_value_from_key as safe_pop


# lots of returned objects are full of tracking params, client data, duplicate info, etc. this sorta trims the fat.
def clean_content_text(content):
    for item in safe(content, "runs", default=[]):
        if "navigationEndpoint" in item:
            # traditional links
            if "urlEndpoint" in item["navigationEndpoint"]:
                url = item["navigationEndpoint"]["urlEndpoint"]["url"]
                # replace redirects with direct links
                if url.startswith("https://www.youtube.com/redirect"):
                    parsed_url = urlparse(url)
                    redirect_url = parse_qs(parsed_url.query)["q"][0]
                    url = unquote(redirect_url)
                item["urlEndpoint"] = {"url": url}
                item.pop("navigationEndpoint")
            # hashtags
            elif "browseEndpoint" in item["navigationEndpoint"]:
                item.pop("loggingDirectives")
                safe_pop(item, "navigationEndpoint", "browseEndpoint", "params")
                item["browseEndpoint"] = item["navigationEndpoint"]["browseEndpoint"]
                item["browseEndpoint"]["url"] = item["navigationEndpoint"]["commandMetadata"]["webCommandMetadata"]["url"]
                item.pop("navigationEndpoint")
    return content

def clean_backstage_attachment(attachment):
    if attachment:
        if "pollRenderer" in attachment:
            for choice in attachment["pollRenderer"]["choices"]:
                for value in [
                    "selectServiceEndpoint",
                    "deselectServiceEndpoint",
                    "voteRatioIfSelected",
                    "votePercentageIfSelected",
                    "voteRatioIfNotSelected",
                    "votePercentageIfNotSelected"
                ]:
                    safe_pop(choice, value)
        elif "videoRenderer" in attachment:
            safe_pop(attachment, "videoRenderer", "navigationEndpoint", "watchEndpoint", "watchEndpointSupportedOnesieConfig")
            attachment["videoRenderer"]["watchEndpoint"] = safe(attachment, "videoRenderer", "navigationEndpoint", "watchEndpoint", default={})
            attachment["videoRenderer"]["watchEndpoint"]["url"] = safe(
                attachment, "videoRenderer", "navigationEndpoint", "commandMetadata", "webCommandMetadata", "url"
            )

            for long_by_line in safe(attachment, "videoRenderer", "longBylineText", "runs", default=[]):
                if "browseEndpoint" in long_by_line["navigationEndpoint"]:
                    long_by_line["browseEndpoint"] = long_by_line["navigationEndpoint"]["browseEndpoint"]
                else:
                    browseEndpoints = []
                    for list_item in safe(long_by_line, "navigationEndpoint", "showDialogCommand", "panelLoadingStrategy", "inlineContent", "dialogViewModel", "customContent", "listViewModel", "listItems", default=[]):
                        browseEndpoints += list_item["listItemViewModel"]["rendererContext"]["commandContext"]["onTap"]["innertubeCommand"]["browseEndpoint"]
                    if browseEndpoints:
                        long_by_line["browseEndpoints"] = browseEndpoints
                long_by_line.pop("navigationEndpoint")

            for short_by_line in safe(attachment, "videoRenderer", "shortBylineText", "runs", default=[]):
                if "browseEndpoint" in short_by_line["navigationEndpoint"]:
                    short_by_line["browseEndpoint"] = short_by_line["navigationEndpoint"]["browseEndpoint"]
                else:
                    browseEndpoints = []
                    for list_item in safe(short_by_line, "navigationEndpoint", "showDialogCommand", "panelLoadingStrategy", "inlineContent", "dialogViewModel", "customContent", "listViewModel", "listItems", default=[]):
                        browseEndpoints += list_item["listItemViewModel"]["rendererContext"]["commandContext"]["onTap"]["innertubeCommand"]["browseEndpoint"]
                    if browseEndpoints:
                        short_by_line["browseEndpoints"] = browseEndpoints
                short_by_line.pop("navigationEndpoint")

            for author in safe(attachment, "videoRenderer", "ownerText", "runs", default=[]):
                if "browseEndpoint" in author["navigationEndpoint"]:
                    author["browseEndpoint"] = author["navigationEndpoint"]["browseEndpoint"]
                else:
                    browseEndpoints = []
                    for list_item in safe(author, "navigationEndpoint", "showDialogCommand", "panelLoadingStrategy", "inlineContent", "dialogViewModel", "customContent", "listViewModel", "listItems", default=[]):
                        browseEndpoints += list_item["listItemViewModel"]["rendererContext"]["commandContext"]["onTap"]["innertubeCommand"]["browseEndpoint"]
                    if browseEndpoints:
                        author["browseEndpoints"] = browseEndpoints

            for value in [
                "publishedTimeText",
                "navigationEndpoint",
                "trackingParams",
                "showActionMenu",
                "menu",
                "channelThumbnailSupportedRenderers",
                "thumbnailOverlays"
            ]:
                safe_pop(attachment, "videoRenderer", value)
        elif "backstageImageRenderer" in attachment:
            safe_pop(attachment, "backstageImageRenderer", "trackingParams")
        elif "postMultiImageRenderer" in attachment:
            for image in attachment["postMultiImageRenderer"]["images"]:
                safe_pop(image, "backstageImageRenderer", "trackingParams")
        return attachment
    return None
