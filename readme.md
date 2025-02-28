# YouTube Community Tab

This repo includes a fork of [bot-jonas/youtube-community-tab](https://github.com/bot-jonas/youtube-community-tab), as well as a script to scrape and dump community tab posts as .json files, along with all attached images and thumbnails.

## Setup / Update

Since this version of the youtube-community-tab package is slightly modified, you will need to install/update it from this repo to guarantee compatibility.
```sh
cd youtube-community-tab
pip install .
```

## Example Usage

```sh
python ytct.py --cookies cookies-youtube-com.txt -d "./Ninomae Ina_nis Ch. hololive-EN" https://www.youtube.com/channel/UCMwGHR0BTZuLsmjY_NT5Pwg/community
OR
./ytct.py --cookies cookies-youtube-com.txt -d "./Ninomae Ina_nis Ch. hololive-EN" https://www.youtube.com/@NinomaeInanis/community
```

## Arguments

```
-h, --help                    show this help message and exit
--cookies COOKIES FILE        a Netscape format cookies file, allows the script to
                              retrieve Membership-only posts
-d, --directory DIRECTORY     save directory (defaults to current)
--post-archive FILE           download only posts not listed in the archive file
                              and record the IDs of newly downloaded posts
--dates                       write information about the post publish date
-r, --reverse                 set download order from oldest to newest post.
```
