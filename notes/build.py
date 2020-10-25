import json
import jinja2
import os
import glob
import shutil
import shortuuid
from ftfy import fix_encoding
import re
from pyhiccup.core import convert
import pprint
from re import search
from bs4 import BeautifulSoup
from jsonpath_ng import jsonpath, parse
from urlextract import URLExtract
import urllib

pp = pprint.PrettyPrinter(indent=4)

templateLoader = jinja2.FileSystemLoader(searchpath="./templates")
env = jinja2.Environment(loader=templateLoader, extensions=['jinja2_highlight.HighlightExtension'])

wordcount = 0

page_uuids = {}
page_names = {}

block_ids = {}

references = {}
_linksTo = []

page_data = {}
private_blocks = {}
private_pages = {}
hiddenTags = ['#personal', '#agenda', '#EntryPoint']


def collectIDs(page):
    '''Collects page names and UUIDs'''
    pagestring = json.dumps(page)

    # generate UUID for page name
    uuid = shortuuid.uuid(name=page['title'])[:8]

    # only remove/skip page if private tag in page attributess
    personalSearch = search(".*Tags::.*#personal.*", pagestring)
    if personalSearch is not None:
        # print('Private page: [[' + page['title'] + ']]')
        private_pages[page['title']] = uuid
        return

    collectChildIDs(page)

    page_uuids[page['title']] = uuid
    page_names[uuid] = page['title']


def collectChildIDs(object):
    '''Collects block children names and UUIDs'''
    if 'children' in object.keys():
        for child in object['children']:
            # only remove block if private tag in block
            # todo is this necessary?
            for tag in hiddenTags:
                result = search(".*" + tag + ".*", child['string'])
                personalSearch = None
                if result is not None:
                    personalSearch = True
                    break

            if personalSearch is not None:
                private_blocks[child['uid']] = child
                collectChildIDs(child)
            else:
                block_ids[child['uid']] = child
                collectChildIDs(child)


def processPage(page):
    title = page['title']
    last_edited = page['edit-time']
    if title not in page_uuids:
        return
    uuid = page_uuids[title]

    children = []
    if 'children' in page.keys():
        for child in page['children']:
            # find the last time the page was edited
            try:
                if child['edit-time'] > last_edited:
                    last_edited = child['edit-time']
            except KeyError:
                if child['create-time'] > last_edited:
                    last_edited = child['create-time']
            if 'heading' in child:
                heading = child['heading']
            else:
                heading = False
            if 'text-align' in child:
                alignment = child['text-align']
            else:
                alignment = False
            # check for private parent blocks and remove block if necessary
            for tag in hiddenTags:
                result = search(".*" + tag + ".*", child['string'])
                personalSearch = None
                if result is not None:
                    personalSearch = True
                    break

            if personalSearch is not None:
                pass
            else:
                children.append({
                    'html': renderMarkdown(fix_encoding(child['string']), heading=heading, alignment=alignment) + renderBullets(child)
                })
    template_data = {
        'title': renderMarkdown(title, ignoreLinks=True),
        'blocks': children,
        'uuid': uuid,
        'last_edited': last_edited,
        'references': []
    }

    global _linksTo

    for item in _linksTo:
        item['link_from'] = uuid
        item['title'] = renderMarkdown(title, ignoreLinks=True)
        item['text'] = renderMarkdown(item['text'], ignoreLinks=True)
        # print(item['text'])
        # item['text'] = item['text']
        # print(item['text'])

        # if item['uuid'] == uuid:
        #    continue

        if item['link_to'] in references.keys():
            references[item['link_to']].append(item)
        else:
            references[item['link_to']] = [item]

    _linksTo = []

    page_data[title] = template_data


def renderPage(page, directory='./', template='template.html', filename='index.html'):
    templateHTML = env.get_template(template)
    if page['title'] not in page_data:
        return

    template_data = page_data[page['title']]
    template_data['website_wordcount'] = wordcount
    template_data['website_pages'] = len(page_names)
    uuid = template_data['uuid']

    if uuid in references:
        template_data['references'] = references[uuid]

    outputHTML = templateHTML.render(**template_data)
    # create the file directory for the page
    os.makedirs(os.path.join(directory, template_data['uuid']), exist_ok=True)
    # save the rendered html page
    with open(os.path.join(directory, template_data['uuid'], filename), 'w') as f:
        f.write(outputHTML)
        f.close()


def renderBullets(block):
    # todo rework this to use beautiful soup
    if 'children' not in block.keys():
        return ''

    output = '<ul id="%s">' % (block['uid'])  # add blockid to div to allow for anchor linking
    # soup = BeautifulSoup("<ul></ul>", features="html.parser")
    # new_li = soup.new_tag('li')
    # new_l = soup.new_tag('li')
    # soup.ul.insert_after(new_li)
    # soup.insert(0, new_li)
    # soup.insert(0, new_l)
    # print(soup)
    for child in block['children']:
        if child['uid'] in private_blocks:
            pass
        else:
            output += '<li id="%s">' % (child['uid'])  # add blockid to div to allow for anchor linking
            if 'heading' in child:
                heading = child['heading']
            else:
                heading = False
            if 'text-align' in child:
                alignment = child['text-align']
            else:
                alignment = False
            output += renderMarkdown(child['string'], heading=heading, alignment=alignment)
            # print(output)
            # new_li = soup.new_tag('li')
            # new_li.string = renderMarkdown(child['string'], heading=heading)
            # soup.ul.append(new_li)

            if 'children' in child.keys():
                output += renderBullets(child)
            output += '</li>'
            # if 'text-align' in child:
            #     # soup = BeautifulSoup(output, features="html.parser")
            #     # soup.find('li')['style'] = ''
            #     # alignment = child['text-align']
            #     # soup = BeautifulSoup(output, features="html.parser")
            #     # soup.find('li')['style'] = child['text-align']
            #     # output = str(soup)
            #     # print(output)
            # else:
            #     alignment = False

    output += '</ul>'
    return output


def _processInternalLink(match, block):
    '''
        Processes Pages that look like this
        [[Page Name]]
    '''
    name = match.group(1)
    # todo include # in text to allow for tag css targeting
    if name in page_uuids:
        uuid = page_uuids[name]
        _linksTo.append({'link_to': uuid, 'text': block})

        return '<a class="internal" data-uuid="' + uuid + '" href="/' + uuid + '">' + renderMarkdown(name) + '</a>'
    else:
        return '<a class="internal private" href="#">' + renderMarkdown(name) + '</a>'
        pass


def _processInternalTag(match, block):
    '''
    Processes tags that look like this
    #tag
    #[[multi word tag]]
    '''
    link = match.group(1)
    name = match.group(2)
    # todo include # in text to allow for tag css targeting
    if name in page_uuids:
        uuid = page_uuids[name]
        _linksTo.append({'link_to': uuid, 'text': block})
        return '<a class="internal tag" data-tag="' + name + '" data-uuid="' + uuid + '" href="/' + uuid + '">#' + name + '</a>'
    else:
        return '<a class="internal private tag" href="#">#' + name + '</a>'
        pass


def _processInternalAlias(match, block):
    '''Processes aliases that look like this [Basic Alias]([[Theme Tester]])'''
    name = match.group(1)
    internal = match.group(2)

    if internal in page_uuids:
        uuid = page_uuids[internal]
        _linksTo.append({'link_to': uuid, 'text': block})
        return '<a class="internal-alias" data-uuid="' + uuid + '" href="/' + uuid + '">' + renderMarkdown(name) + '</a>'
    else:
        return '<a class="internal private" href="#">' + renderMarkdown(name) + '</a>'


def _findChildParent(blockID):
    '''This is super hacky jsonpath can probably just do this a fancy query'''
    # I need the root title where one of the children has a value of JF3iFJPKu
    # https://pypi.org/project/jsonpath-ng/
    with open(jsonFile, 'r') as f:
        data = json.loads(f.read())

    # find all blocks with UIDs
    jsonpath_expression = parse("$..uid")

    match = jsonpath_expression.find(data)
    for m in match:
        # target block with correct UID
        if m.value == blockID:
            # get full tree path for block
            fullPath = str(m.full_path)
            # some super hacky stuff to get the index of the page that the blockID is on
            s = {"[", "]"}
            parent = int(fullPath.split(".")[0].strip("[").strip("]"))
            string = m.context.value["string"]
            # print("parent title is " + data[parent]['title'])
            # print("block id is " + m.value)
            # search to see if the parent is a private page
            if data[parent]['title'] in page_uuids:
                private = False
            else:
                private = True
            try:
                return page_uuids[data[parent]['title']], private, string
            except KeyError:
                return private_pages[data[parent]['title']], private, string
        else:
            pass


def _processInternalBlockAlias(match, block):
    '''Processes aliases that look like this [Block Alias](((JF3iFJPKu)))'''
    name = renderMarkdown(match.group(1))
    internalBlock = match.group(2)
    parent = _findChildParent(internalBlock)
    try:
        parentUID = parent[0]
        private = parent[1]
        # todo bad block links cause this process to fail. Fix this ^^__Quick link to__ [Conversations:](
        # todo fix block anchoring
        try:
            if not private:
                # print("not private internal block alias")
                return('<a class="internal-block embed" data-uuid="' + parentUID + '" href="/' + parentUID + '#' + internalBlock + '">' + name + '</a>')
            else:
                # print('private internal block alias')
                return ('<a class="internal-block private" data-uuid="' + parentUID + '" href="/' + parentUID + '">' + name + '</a>')
        except Exception as e:
            print(name)
            print(parentUID)
            print(e)
            print("---")
        return '<a class="internal-block embed" data-uuid="' + parentUID + '" href="/' + parentUID + '#' + internalBlock + '">' + name + '</a>'
    except TypeError:
        # print('private internal block alias')
        return f'<a class="internal-block private" >{name}</a>'


def _processInternalEmbed(match, block):
    '''
        Processes clojure elements that look like this
        {{[[embed]]: ((sHQRa0Wan))}}
        {{alias: ((kgjAyPp0Z)) Clojure Block Alias}}
    '''
    name = renderMarkdown(match.group(1))
    blockID = match.group(2)

    parent = _findChildParent(blockID)
    try:
        parentUID = parent[0]
        private = parent[1]
        string = parent[2]

        # todo there's no error handling here, what if the embed it from a private page?
        # return f'<span class="internal embed">{renderMarkdown(m.context.value["string"])}</span>'
        return f'<a class="internal embed" href="/{parentUID}#{blockID}">{renderMarkdown(string)}</a>'
    except TypeError:
        return f'<a class="internal embed private" href="">{blockID}</a>'


def _processInternaPagelEmbed(match, block):
    '''
        Processes clojure elements that look like this
        {{alias: [[Theme Tester]] Clojure Page Alias}}

    '''
    name = renderMarkdown(match.group(1))
    pageName = match.group(2)
    string = match.group(3)
    try:
        parentUID = page_uuids[pageName]
        # todo there's no error handling here, what if the embed it from a private page?
        # return f'<span class="internal embed">{renderMarkdown(m.context.value["string"])}</span>'
        return f'<a class="internal embed" href="/{parentUID}">{renderMarkdown(string)}</a>'
    except TypeError:
        return f'<a class="internal embed private" href="">{parentUID}</a>'


def _processExternalAlias(match, block):
    # print(match.group(2))
    # r'<a class="external" href="/2" target="_blank">\1</a>
    return f'<a class="external" href="{match.group(2)}" target="_blank">{match.group(1)}</a>'


def _processBareURL(url):
    # deal with protocallless urls
    if not urllib.parse.urlparse(url).scheme:
        url = 'http://' + url
    # deal with custom twitter embedding
    if "twitter.com" in url:
        return f'<blockquote class="twitter-tweet"><a href="{url}"></a></blockquote> <script async src="https://platform.twitter.com/widgets.js" charset="utf-8"></script>'
    try:
        # find the title of the page to use for the link title
        soup = BeautifulSoup(urllib.request.urlopen(url), features="html.parser")
        link_title = soup.title.string[:35]
        if len(soup.title.string) > 35:
            link_title = link_title + '...'
    except Exception as e:
        # if page has no 'title' use a shortend version of the url
        if len(url) > 25:
            link_title = url[:25] + '...'
        else:
            link_title = url
    # print(link_title)
    return f'<a class="external" href="{url}" target="_blank">{link_title}</a>'


def _processExternalEmbed(match, block, type):
    '''
        Processes external clojure embeds that look like this
        {{[[youtube]]: https://www.youtube.com/watch?v=1otcGrYVSag}}
    '''
    if type is "youtube":
        externalLink = renderMarkdown(match.group(1))
        return f'<iframe width="420" height="315" src="{externalLink}"></iframe>'


def _processAttribute(match, block):
    '''
        Processes attributes that look like this
        Attribute::
    '''
    # TODO save attributes for specific templates
    name = renderMarkdown(match.group(1))
    return f'<span class="attribute">{name}::</span>'


def _processTextVersion(match, block):
    '''Processes in-line text versioning that looks like this {{or: first choice|second choice}}'''
    text = renderMarkdown(match.group(2))
    textOptions = text.split("|")
    options = ''
    for o in textOptions:
        option = f'<option value="{o}">{o}</option>'
        options += option
    select = f'<select class="text-versioning">{options}</select>'
    return select


def renderMarkdown(text, ignoreLinks=False, heading=False, alignment=False):
    if ':hiccup' in text:
        # THIS DOES NOT WORK WELL !!! VERY BROKEN
        # text = 'hr '
        data = re.sub(r'\n', '', text.strip())
        data = re.sub(r':hiccup \[:hr\]', r'<hr>', data)
        data = re.sub(r'(\[\s*?):([\w-]+)', r'\1"\2",', data)
        data = re.sub(r':([\w-]+)', r'"\1":', data)
        data = re.sub(r'([\}\]\:][\s]*?)(\w+)([\s]*?[\[\{\]])', r'\1"\2"\3', data)
        data = re.sub(r'([\}\]\"])([\s\n]*?)([\[\{\"])', r'\1,\2\3', data)
        # print(data[9:])
        # data = re.sub(r'(hr)', r'hr', data)  # this tag is not being converted correctly

        # print(data[10:])
        # print(json.loads(data[10:]))
        # print(convert(data))
        # return convert(data)
        return data

    if ignoreLinks is False:
        global wordcount
        wordcount += len(text.split())
    # todo correctly render page alias {{alias: [[Roam Research]] Roam}}
    # todo fix URLs that contain a #
    text = re.sub(r'\b(.+)\:\:', lambda x: _processAttribute(x, text), text)  # attributes
    text = re.sub(r'{{\[\[TODO\]\]}}', r'<input type="checkbox" onclick="return false;">', text)  # unchecked TO DO
    text = re.sub(r'{{{\[\[DONE\]\]}}}}', r'<input type="checkbox" onclick="return false;" checked>', text)  # checked TO DO alt
    text = re.sub(r'{{\[\[DONE\]\]}}', r'<input type="checkbox" onclick="return false;" checked>', text)  # checked TO DO
    text = re.sub(r'\!\[([^\[\]]*?)\]\((.+?)\)', r'<img src="\2" alt="\1" />', text)  # markdown images
    text = re.sub(r'\{\{\[\[youtube\]\]:(.+?)\}\}', lambda x: _processExternalEmbed(x, text, "youtube"), text)  # external clojure embeds
    text = re.sub(r'\{\{(.*):.*[^\{\}]\((.+?)\)\)(.*)\}\}', lambda x: _processInternalEmbed(x, text), text)  # clojure embeds and Block aliases \{\{(.*):.*([^\{\}]\(.+?\)\)).*\}\}
    text = re.sub(r'\{\{(.*):.*[^\{\}]\[(.+?)\]\](.*)\}\}', lambda x: _processInternaPagelEmbed(x, text), text)  # clojure page aliases

    text = re.sub(r'(\{\{or:(.+?)\}\})', lambda x: _processTextVersion(x, text), text)  # text versioning

    if ignoreLinks:
        text = re.sub(r'\[\[(.+?)\]\]', r'\1', text)  # page links
        text = re.sub(r'\[([^\[\]]+?)\]\((.+?)\)', r'\1', text)  # external links
        text = re.sub(r'\b(.+)\:\:', lambda x: _processAttribute(x, text), text)  # attributes

    else:
        text = re.sub(r'\[([^\[\]]+?)\]\(\[\[(.+?)\]\]\)', lambda x: _processInternalAlias(x, text), text)  # internal page aliases
        text = re.sub(r'\[([^\[\]]+?)\]\(\(\((.+?)\)\)\)', lambda x: _processInternalBlockAlias(x, text), text)  # internal block aliases
        text = re.sub(r'\[([^\[\]]+?)\]\(([^\[\]\(].+?)\)', lambda x: _processExternalAlias(x, text), text)  # external aliases
        text = re.sub(r'(?<!href="\/[A-Za-z0-9\-\_]{8})(#(\w+))', lambda x: _processInternalTag(x, text), text)  # tags without brackets

        text = re.sub(r'(\#\[\[(.+?)\]\])', lambda x: _processInternalTag(x, text), text)  # tag with brackets
        text = re.sub(r'(?<!\#)\[\[(.+?)\]\]', lambda x: _processInternalLink(x, text), text)  # pages with brackets

    text = re.sub(r'\n', r'<br>', text)  # newline
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)  # bold
    text = re.sub(r'\_\_(.*?)\_\_', r'<em>\1</em>', text)  # italic
    text = re.sub(r'\~\~(.+?)\~\~', r'<s>\1</s>', text)  # strikethrough
    text = re.sub(r'\^\^(.+?)\^\^', r'<span class="highlight">\1</span>', text)  # highlight
    text = re.sub(r'\`\`\`(.+?)\`\`\`', r'<code>\1</code>', text)  # large codeblock
    text = re.sub(r'\`(.+?)\`', r'<code>\1</code>', text)  # inline codeblock

    def isBlockPrivate(blockID, blockText):
        if blockID in block_ids:
            # print("block not private")
            # print(blockText)
            # print(blockID)
            return renderMarkdown(block_ids[blockID]['string'])
        else:
            # print("block is private")
            # print(blockText)
            pass

    text = re.sub(r'\(\((.+?)\)\)', lambda x: isBlockPrivate(x.group(1), text), text)  # block ref

    # deal with bare URLs
    # not a huge fan of this
    forbidden_chars = ['<a', '<img', '[', '<code', '<iframe']
    results = []
    for substring in forbidden_chars:
        results.append(substring in text)
    if not any(results):
        extractor = URLExtract()
        if extractor.has_urls(text):
            for url in extractor.gen_urls(text):
                text = text.replace(url, _processBareURL(url))
                # print(text)

    if heading:
        text = f'<h{heading}>{text}</h{heading}>'
    if alignment:
        text = f'<div style="text-align:{alignment};">{text}</div>'
    return text


# load json backup
jsonFile = 'Theme Tester.json'
# jsonFile = 'MattPublic.json'

# read database json
with open(jsonFile, 'r') as f:
    data = json.loads(f.read())
for page in data:  # get page ids
    collectIDs(page)

for page in data:
    processPage(page)

pagecount = len(page_data.keys())
# remove all files in public folder. these will be regenerated later
files = glob.glob('./public/*')
for f in files:
    if os.path.isdir(f):
        shutil.rmtree(f)
    else:
        os.remove(f)

# initialize build directory
src_files = os.listdir('./www')
for file_name in src_files:
    full_file_name = os.path.join('./www', file_name)
    if os.path.isfile(full_file_name):
        shutil.copy(full_file_name, './public')
    elif os.path.isdir(full_file_name):
        shutil.copytree(full_file_name, os.path.join('./public', file_name))


def _checkNamespace(page):
    '''checks for namespaces with specific templates'''

    namespace_split = page['title'].split("/")
    if len(namespace_split) > 1:
        if namespace_split[0] == 'Book':
            template = namespace_split[0].lower() + '_template.html'
            # print(template)
            return template
    else:
        return False


for page in data:
    template_name = 'template.html'
    namespace_template = _checkNamespace(page)
    if namespace_template:
        template_name = namespace_template
    # TODO create new templates
    # TODO use correct template
    # TODO figure out how templating works
    renderPage(page, './public', template='template.html')
    renderPage(page, './public', template='embed.html', filename='embed.html')
    renderPage(page, './public', template='page.html', filename='page.html')
    try:
        template_data = page_data[page['title']]
        # print(len(template_data["references"]))
    except Exception:
        pass


# run through twice so that you can put jinja/html directly into Notion
# perhaps this feature could be made optional
# template = env.from_string(outputHTML)
# outputHTML = template.render(**template_data)
