# -*- coding: utf-8 -*-
import pprint
import edn_format
import datetime
import json
from subprocess import Popen, PIPE, STDOUT
pp = pprint.PrettyPrinter(indent=4)

ednFile = "MattPublic_pretty.edn"
data = edn_format.loads(open(ednFile).read())


def searchChildren(blockID, viewType=None):
    child = {}
    for sublist in data:
        if sublist[0] == blockID:
            child['entity/id'] = blockID
            if sublist[1]._name == "block/children":
                subchild = searchChildren(sublist[2])
                # testPage["block/children"] = append(sublist[2])
                # child.setdefault("block/children", []).append(sublist[2])
                child.setdefault("children", []).append(subchild)
            elif sublist[1]._name == "node/title":
                child["title"] = str(sublist[2])
            elif sublist[1]._name == "edit/time":
                child["edit-time"] = int(sublist[2])
            elif sublist[1]._name == "create/time":
                child["create-time"] = int(sublist[2])
            elif sublist[1]._name == "block/uid":
                child["uid"] = str(sublist[2])
            elif sublist[1]._name == "block/string":
                child["string"] = str(sublist[2])
            elif sublist[1]._name == "block/heading":
                child["heading"] = int(sublist[2])
            elif sublist[1]._name == "block/text-align":
                child["text-align"] = str(sublist[2])
            elif sublist[1]._name == "block/props":
                child["props"] = str(sublist[2])
            elif sublist[1]._name == "children/view-type":
                child["view-type"] = str(sublist[2])
            elif sublist[1]._name == "block/order":
                child["order"] = int(sublist[2])
            else:
                # testPage[str(sublist[1]._name)] = "true"
                child[str(sublist[1]._name)] = str(sublist[2])
    return child


def main():
    ednFile = "MattPublic.edn"
    with open(ednFile, 'r+') as f:
        content = f.read()
        # split out unneeded info from beginning and end of file
        content = content.split(":datoms ")[1][:-1]
        data = edn_format.loads(content)
    print(type(data))
    search = 24
    # for sublist in data:
    #     if sublist[0] == search:
    #         print(type(sublist[1]._name))
    pages = []
    search = 'node/title'
    for sublist in data:
        if sublist[1]._name == search:
            # print(sublist[2])
            individPage = {}
            for s in data:
                if s[0] == sublist[0]:
                    individPage["entity/id"] = s[0]
                    # testPage.append(sublist)
                    if s[1]._name == "block/children":
                        child = searchChildren(s[2])
                        individPage.setdefault("children", []).append(child)
                    elif s[1]._name == "node/title":
                        individPage["title"] = str(s[2])
                    elif s[1]._name == "edit/time":
                        individPage["edit-time"] = int(s[2])
                    elif s[1]._name == "create/time":
                        individPage["create-time"] = int(s[2])
                    elif s[1]._name == "block/uid":
                        individPage["uid"] = str(s[2])
                    elif s[1]._name == "block/string":
                        individPage["string"] = str(s[2])
                    elif s[1]._name == "block/heading":
                        individPage["heading"] = int(s[2])
                    elif s[1]._name == "block/text-align":
                        individPage["text-align"] = str(s[2])
                    elif s[1]._name == "children/view-type":
                        individPage["view-type"] = str(s[2])
                    elif s[1]._name == "block/order":
                        individPage["order"] = int(s[2])
                    else:
                        individPage[str(s[1]._name)] = str(s[2])
            pages.append(individPage)

    with open('About.json', 'w') as f:
        # todo sort by block/
        json.dump(pages, f, indent=4, separators=(',', ': '), ensure_ascii=False)


def tester():
    testerNumber = 450
    # testerNumber = 230
    testPage = {}

    for sublist in data:
        if sublist[0] == testerNumber:
            testPage["entity/id"] = testerNumber
            # testPage.append(sublist)
            if sublist[1]._name == "block/children":
                child = searchChildren(sublist[2])
                # testPage["block/children"] = append(sublist[2])
                testPage.setdefault("children", []).append(child)
            elif sublist[1]._name == "node/title":
                testPage["title"] = str(sublist[2])
            elif sublist[1]._name == "edit/time":
                testPage["edit-time"] = int(sublist[2])
            elif sublist[1]._name == "create/time":
                testPage["create-time"] = int(sublist[2])
            elif sublist[1]._name == "block/uid":
                testPage["uid"] = str(sublist[2])
            elif sublist[1]._name == "block/string":
                testPage["string"] = str(sublist[2])
            elif sublist[1]._name == "block/heading":
                testPage["heading"] = int(sublist[2])
            elif sublist[1]._name == "block/text-align":
                testPage["text-align"] = str(sublist[2])
            elif sublist[1]._name == "children/view-type":
                testPage["view-type"] = str(sublist[2])
            elif sublist[1]._name == "block/order":
                testPage["order"] = int(sublist[2])
            else:
                testPage[str(sublist[1]._name)] = str(sublist[2])
    # pp.pprint(testPage)
    # pp.pprint(json.dumps(testPage))
    with open('About.json', 'w') as f:
        json.dump([testPage], f, indent=4, separators=(',', ': '), ensure_ascii=False)
        # json.dump([testPage], f, ensure_ascii=False)


def pretty(ednFile):
    # ednFile = "MattPublic.edn"
    with open(ednFile, 'r+') as f:
        content = f.read()
        # split out unneeded info from beginning and end of file
        content = content.split(":datoms ")[1][:-1]
        try:
            jet = Popen(
                ["jet", "--edn-reader-opts", "{:default tagged-literal}", "--pretty"],
                stdout=PIPE, stdin=PIPE, stderr=STDOUT)
            jet_stdout, _ = jet.communicate(input=str.encode(content))
            content = jet_stdout.decode()
        except IOError as e:
            print(e)
            print("Jet not installed, skipping EDN pretty printing")

        e = open("/Users/mtvogel/Downloads/MattVogel_pretty.edn", "w")
        e.write(content)
        e.close()


if __name__ == '__main__':
    # pretty("/Users/mtvogel/Downloads/MattVogel.edn")
    main()
    # tester()
