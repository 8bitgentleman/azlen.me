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
    # TODO if tagged private remove children under tag
    if 'children' in object.keys():
        for child in object['children']:
            # block_ids[child['uid']] = child
            # only remove block if private tag in block
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
    if 'children' not in block.keys():
        return ''

    output = '<ul>'
    soup = BeautifulSoup("<ul></ul>", features="html.parser")
    new_li = soup.new_tag('li')
    new_l = soup.new_tag('li')
    # soup.ul.insert_after(new_li)
    # soup.insert(0, new_li)
    # soup.insert(0, new_l)
    # print(soup)
    for child in block['children']:
        if child['uid'] in private_blocks:
            pass
        else:
            output += '<li>'
            if 'heading' in child:
                heading = child['heading']
            else:
                heading = False
            output += renderMarkdown(child['string'], heading=heading)
            new_li = soup.new_tag('li')
            new_li.string = renderMarkdown(child['string'], heading=heading)
            soup.ul.append(new_li)
            # print(new_li)
            # print(output)
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
    # print(output)
    return output


def _processInternalLink(match, block):
    name = match.group(1)
    if name in page_uuids:
        uuid = page_uuids[name]
        _linksTo.append({'link_to': uuid, 'text': block})
        return '<a class="internal" data-uuid="' + uuid + '" href="/' + uuid + '">' + renderMarkdown(name) + '</a>'
    else:
        return '<a class="internal private" href="#">' + renderMarkdown(name) + '</a>'


def _processInternalAlias(match, block):
    name = match.group(1)
    internal = match.group(2)

    if internal in page_uuids:
        uuid = page_uuids[internal]
        _linksTo.append({'link_to': uuid, 'text': block})
        return '<a class="internal" data-uuid="' + uuid + '" href="/' + uuid + '">' + renderMarkdown(name) + '</a>'
    else:
        return '<a class="internal private" href="#">' + renderMarkdown(name) + '</a>'


def renderMarkdown(text, ignoreLinks=False, heading=False, alignment=False):
    if ':hiccup' in text:
        # THIS DOES NOT WORK WELL !!! VERY BROKEN
        # TODO render hiccup hr
        print(text)
        # text = 'hr '
        data = re.sub(r'\n', '', text.strip())
        data = re.sub(r'(\[\s*?):([\w-]+)', r'\1"\2",', data)
        data = re.sub(r':([\w-]+)', r'"\1":', data)
        data = re.sub(r'([\}\]\:][\s]*?)(\w+)([\s]*?[\[\{\]])', r'\1"\2"\3', data)
        data = re.sub(r'([\}\]\"])([\s\n]*?)([\[\{\"])', r'\1,\2\3', data)
        print(data[9:])
        # data = re.sub(r'(hr)', r'hr', data)  # this tag is not being converted correctly

        # print(data[9:])

        # print(data[10:])
        # print(json.loads(data[10:]))
        return convert(text)

    if ignoreLinks is False:
        global wordcount
        wordcount += len(text.split())

    text = re.sub(r'{{\[\[TODO\]\]}}', r'<input type="checkbox" onclick="return false;">', text)  # unchecked TO DO
    text = re.sub(r'{{\[\[DONE\]\]}}', r'<input type="checkbox" onclick="return false;" checked>', text)  # unchecked TO DO
    text = re.sub(r'\!\[([^\[\]]*?)\]\((.+?)\)', r'<img src="\2" alt="1" />', text)  # markdown images
    if ignoreLinks:
        text = re.sub(r'\[\[(.+?)\]\]', r'\1', text)  # page links
        text = re.sub(r'\[([^\[\]]+?)\]\((.+?)\)', r'\1', text)  # external links
    else:
        text = re.sub(r'\[([^\[\]]+?)\]\(([^\[\]].+?)\)', r'<a class="external" href="\2" target="_blank">\1</a>', text)  # external aliases
        text = re.sub(r'\[([^\[\]]+?)\]\(\[\[(.+?)\]\]\)', lambda x: _processInternalAlias(x, text), text)  # internal aliases

        text = re.sub(r'\[\[(.+?)\]\]', lambda x: _processInternalLink(x, text), text)  # pages with brackets
        text = re.sub(r'(?<=#)(\w+)', lambda x: _processInternalLink(x, text), text)  # tags without brackets

    text = re.sub(r'\n', r'<br>', text)  # newline
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)  # bold
    text = re.sub(r'\_\_(.*?)\_\_', r'<em>\1</em>', text)  # italic
    text = re.sub(r'\~\~(.+?)\~\~', r'<s>\1</s>', text)  # strikethrough
    text = re.sub(r'\^\^(.+?)\^\^', r'<span class="highlight">\1</span>', text)  # highlight
    text = re.sub(r'\`\`\`(.+?)\`\`\`', r'<code>\1</code>', text)  # large codeblock
    text = re.sub(r'\`(.+?)\`', r'<code>\1</code>', text)  # inline codeblock

    text = re.sub(r'\(\((.+?)\)\)', lambda x: renderMarkdown(block_ids[x.group(1)]['string'], ignoreLinks=True), text)  # block ref
    if heading:
        # text = "<h{heading}>" + text + "</h{heading}>"
        text = f'<h{heading}>{text}</h{heading}>'

    return text


def removePrivateBlocks(page):
    print(page)


# load json backup
with open('MattPublic.json', 'r') as f:
    data = json.loads(f.read())
for page in data:  # get page ids
    collectIDs(page)

pp.pprint(list(private_blocks.keys()))


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
