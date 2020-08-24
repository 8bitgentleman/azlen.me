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


def collectIDs(page):
    '''Collects page names and UUIDs'''
    pagestring = json.dumps(page)

    # only remove page if private tag in page attributess
    personalSearch = search(".*Tags::.*#personal.*", pagestring)
    if personalSearch is not None:
        print('Private page: [[' + page['title'] + ']]')
        return

    uuid = shortuuid.uuid(name=page['title'])[:8]
    collectChildIDs(page)

    page_uuids[page['title']] = uuid
    page_names[uuid] = page['title']


def collectChildIDs(object):
    '''Collects block children names and UUIDs'''
    if 'children' in object.keys():
        for child in object['children']:
            # block_ids[child['uid']] = child
            # only remove block if private tag in block
            # todo remove Agenda blocks
            personalSearch = search(".*#personal.*", child['string'])
            if personalSearch is not None:
                print('Private block: "' + child['string'] + '"')
                private_blocks[child['uid']] = child
                collectChildIDs(child)
            else:
                block_ids[child['uid']] = child
                collectChildIDs(child)


def processPage(page):
    title = page['title']
    if title not in page_uuids:
        return
    # print(title)
    uuid = page_uuids[title]

    children = []
    if 'children' in page.keys():
        for child in page['children']:
            if 'heading' in child:
                heading = child['heading']
            else:
                heading = False

            children.append({
                'html': renderMarkdown(fix_encoding(child['string']), heading=heading) + renderBullets(child)
            })
    template_data = {
        'title': renderMarkdown(title, ignoreLinks=True),
        'blocks': children,
        'uuid': uuid,
        'references': []
    }

    global _linksTo

    for item in _linksTo:
        item['link_from'] = uuid
        item['title'] = renderMarkdown(title, ignoreLinks=True)
        item['text'] = renderMarkdown(item['text'], ignoreLinks=True)

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

    os.makedirs(os.path.join(directory, template_data['uuid']), exist_ok=True)

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
            output += renderMarkdown(child['string'], heading=heading)
            # print(output)
            # new_li = soup.new_tag('li')
            # new_li.string = renderMarkdown(child['string'], heading=heading)
            # soup.ul.append(new_li)

            if 'children' in child.keys():
                output += renderBullets(child)
                # print(renderBullets(child))
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
    # print(soup)
    return output


def _processInternalLink(match, block):
    name = match.group(1)
    # todo include # in text to allow for tag css targeting
    if name in page_uuids:
        uuid = page_uuids[name]
        _linksTo.append({'link_to': uuid, 'text': block})

        return '<a class="internal" data-uuid="' + uuid + '" href="/' + uuid + '">' + renderMarkdown(name) + '</a>'
    else:
        return '<a class="internal private" href="#">' + renderMarkdown(name) + '</a>'
        pass


def _processInternalAlias(match, block):
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
            # print("parent title is " + data[parent]['title'])
            # print("block id is " + m.value)
            # search to see if the parent is a private page
            if data[parent]['title'] in page_uuids:
                private = False
            else:
                private = True
            return page_uuids[data[parent]['title']], private
        else:
            pass


def _processInternalBlockAlias(match, block):
    name = renderMarkdown(match.group(1))
    internalBlock = match.group(2)
    # print(name, internal)
    parent = _findChildParent(internalBlock)
    # print("block")
    # print(block)
    # print(match)
    # print("parent ")
    # print(parent)
    parentUID = parent[0]
    private = parent[1]
    # todo bad block links cause this process to fail. Fix this ^^__Quick link to__→ [Conversations:](
    # todo fix block anchoring
    # todo this may need to be reworked to account for out of bounds blocks
    try:
        if not private:
            # print("not private internal block alias")
            return('<a class="internal-block" data-uuid="' + parentUID + '" href="/' + parentUID + '">' + name + '</a>')
        else:
            # print('private internal block alias')
            # print('<a class="internal-block private" data-uuid="' + parentUID + '" href="/' + parentUID + '">' + name + '</a>')
            return ('<a class="internal-block private" data-uuid="' + parentUID + '" href="/' + parentUID + '">' + name + '</a>')
    except Exception as e:
        print(name)
        print(parentUID)
        print(e)
        print("---")

    return '<a class="internal-block" data-uuid="' + parentUID + '" href="/' + parentUID + '">' + name + '</a>'


def _processInternalEmbed(match, block):
    name = renderMarkdown(match.group(1))
    blockID = match.group(2)

    with open(jsonFile, 'r') as f:
        data = json.loads(f.read())

    # find all blocks with UIDs
    jsonpath_expression = parse("$..uid")

    match = jsonpath_expression.find(data)
    for m in match:
        # target block with correct UID
        if m.value == blockID:
            return renderMarkdown(m.context.value['string'])


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
    # todo find attributess \b(.+)\:\: and turn them into links
    # todo correctly render page alias {{alias: [[Roam Research]] Roam}}
    text = re.sub(r'{{\[\[TODO\]\]}}', r'<input type="checkbox" onclick="return false;">', text)  # unchecked TO DO
    text = re.sub(r'{{{\[\[DONE\]\]}}}}', r'<input type="checkbox" onclick="return false;" checked>', text)  # checked TO DO alt
    text = re.sub(r'{{\[\[DONE\]\]}}', r'<input type="checkbox" onclick="return false;" checked>', text)  # checked TO DO
    text = re.sub(r'\!\[([^\[\]]*?)\]\((.+?)\)', r'<img src="\2" alt="1" />', text)  # markdown images
    text = re.sub(r'\{\{(.*):.*[^\{\}]\((.+?)\)\).*\}\}', lambda x: _processInternalEmbed(x, text), text)  # clojure embeds and aliases \{\{(.*):.*([^\{\}]\(.+?\)\)).*\}\}
    if ignoreLinks:
        text = re.sub(r'\[\[(.+?)\]\]', r'\1', text)  # page links
        text = re.sub(r'\[([^\[\]]+?)\]\((.+?)\)', r'\1', text)  # external links
    else:
        text = re.sub(r'\[([^\[\]]+?)\]\(\[\[(.+?)\]\]\)', lambda x: _processInternalAlias(x, text), text)  # internal page aliases
        text = re.sub(r'\[([^\[\]]+?)\]\(\(\((.+?)\)\)\)', lambda x: _processInternalBlockAlias(x, text), text)  # internal block aliases
        text = re.sub(r'\[([^\[\]]+?)\]\(([^\[\]\(].+?)\)', r'<a class="external" href="\2" target="_blank">\1</a>', text)  # external aliases
        text = re.sub(r'\#\[\[(.+?)\]\]', lambda x: _processInternalLink(x, text), text)  # tag with brackets
        text = re.sub(r'(?<!\#)\[\[(.+?)\]\]', lambda x: _processInternalLink(x, text), text)  # pages with brackets
        # todo rework regex to allow for # in link text
        text = re.sub(r'(?<=#)(\w+)', lambda x: _processInternalLink(x, text), text)  # tags without brackets

    text = re.sub(r'\n', r'<br>', text)  # newline
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)  # bold
    text = re.sub(r'\_\_(.*?)\_\_', r'<em>\1</em>', text)  # italic
    text = re.sub(r'\~\~(.+?)\~\~', r'<s>\1</s>', text)  # strikethrough
    text = re.sub(r'\^\^(.+?)\^\^', r'<span class="highlight">\1</span>', text)  # highlight
    text = re.sub(r'\`\`\`(.+?)\`\`\`', r'<code>\1</code>', text)  # large codeblock
    text = re.sub(r'\`(.+?)\`', r'<code>\1</code>', text)  # inline codeblock
    try:
        text = re.sub(r'\(\((.+?)\)\)', lambda x: renderMarkdown(block_ids[x.group(1)]['string'], ignoreLinks=True), text)  # block ref
    except Exception as e:
        print("block ref error")
        print(e)
        print(text)
    if heading:
        # text = "<h{heading}>" + text + "</h{heading}>"
        text = f'<h{heading}>{text}</h{heading}>'
    return text


# load json backup
jsonFile = 'MattVogel.json'

with open(jsonFile, 'r') as f:
    data = json.loads(f.read())
for page in data:  # get page ids
    collectIDs(page)

# pp.pprint(list(private_blocks.keys()))

for page in data:
    processPage(page)

pagecount = len(page_data.keys())

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

for page in data:
    renderPage(page, './public', template='template.html')
    renderPage(page, './public', template='embed.html', filename='embed.html')
    renderPage(page, './public', template='page.html', filename='page.html')


# run through twice so that you can put jinja/html directly into Notion
# perhaps this feature could be made optional
# template = env.from_string(outputHTML)
# outputHTML = template.render(**template_data)
