# -*- coding: utf-8 -*-

"""
twp.workbook
-----------------

This module contains logic for parsing tableau workbooks to a readable (and SQL-valid) report


See the README for further details.
"""

from collections import OrderedDict
from datetime import datetime
import getpass
import os
import re
import xml.etree.ElementTree as ET
import zipfile
import pdb


LINE_BIG = 77
LINE_SMALL = 50


def return_xml(filename):
    """Load twb XML into memory & return root object."""
    _validate_file(filename)

    if filename.endswith('.twbx'):
        return _parse_twbx(filename)

    return ET.parse(filename).getroot()


def _validate_file(filename):
    """Validate given file is acceptable for processing."""
    if not os.path.isfile(filename):
        raise OSError('%s is not a valid file path.' % filename)

    if filename.split('.')[-1] not in ('twb', 'twbx'):
        raise OSError('%s is not a valid tableau file.' % filename)


def _parse_twbx(filename):
    """Parse twbx zip & return twb XML."""
    with open(filename, 'rb') as infile:
        twbx = zipfile.ZipFile(infile)

        for item in twbx.namelist():
            if item.endswith('.twb'):
                twb = twbx.open(item)
                return ET.parse(twb).getroot()


def parse_worksheets(worksheets):
    """Parse worksheet xml objects & return cleaned values."""
    results = OrderedDict()

    for worksheet in worksheets:
        name = worksheet.attrib['name']
        datasource = worksheet.find('table/view/datasources')
        datasource = [i.attrib['caption'] for i in datasource if 'caption' in i.attrib]
        results[name] = datasource

    return results


def parse_datasources(datasources):
    """Parse connection xml objects & return cleaned values."""
    results = OrderedDict()
    datasources = [i for i in datasources if 'caption' in i.attrib]

    for datasource in datasources:
        nconns = datasource.findall('.//*/*/named-connection')

        connections = datasource.findall(".//connection[@class='snowflake']")


        name = datasource.attrib['name'] if 'name' in datasource.attrib else None
        caption = datasource.attrib[ 'caption'] if 'caption' in datasource.attrib else None

        if len(connections) > 0:
            conn = connections[0]
            nc = nconns[0]

            datasource_name = nc.attrib['name'] if 'name' in nc .attrib else None
            engine = conn.attrib['class'] if 'class' in conn.attrib else None
            database = conn.attrib['dbname'] if 'dbname' in conn.attrib else None
            server = conn.attrib['server'] if 'server' in conn.attrib else None
            username = conn.attrib['username'] if 'username' in conn.attrib else None
            schema = conn.attrib['schema'] if 'schema' in conn.attrib else None
        else:
            datasource_name = 'No snowflake connection'
            engine = 'No snowflake connection'
            database = 'No snowflake connection'
            server = 'No snowflake connection'
            username = 'No snowflake connection'
            schema = 'No snowflake connection'

        results[name] = {
                'datasource_name': datasource_name,
                'source_name': name,
                'source_caption': caption,
                'engine': engine,
                'db': database,
                'server': server,
                'user': username,
                'schema': schema
                }

    return results


def parse_relations(relations):
    """Parse query&table xml objects & return cleaned values."""
    results = list()

    for relation in relations:
        if relation is None or relation.attrib['type'] == 'join':
            continue

        name = relation.attrib['name']

        query = relation.text if relation.text else '      -- LINKED TO: %s' % relation.attrib['table']

        query = query.replace('<<', '<').replace('>>', '>')

        # TODO: Should be handling for universal newlines better (ie \r\n)
        results.append({
                'query': re.sub(r'\r\n', r'\n', query),
                'connection': relation.attrib['connection'] if 'connection' in relation.attrib else '',
                'table': relation.attrib['table'] if 'table' in relation.attrib else '',
                'type': relation.attrib['type'] if 'type' in relation.attrib else '',
                'name': relation.attrib['name'] if 'name' in relation.attrib else '',
                'datasource_name': relation.attrib['datasource_name'] if 'datasource_name' in relation.attrib else ''
                })

    return results


def format_header(filename):
    """Format header object for outfile."""
    filename = os.path.abspath(filename)
    username = getpass.getuser()
    today = datetime.now().strftime('%Y-%m-%d %I:%M%p')

    output = '%s\n' % ('-'*LINE_BIG)
    output += '-- Created by: %s\n' % username
    output += '-- Created on: %s\n' % today
    output += '-- Source: %s\n' % filename
    output += '%s%s' % ('-'*LINE_BIG, '\n'*3)

    return output


def format_worksheets(worksheets):
    """Format worksheets object for outfile."""
    output = '-- Worksheets w/ Datasources %s\n' % ('-'*(LINE_BIG-29))

    for worksheet in worksheets:
        output += '-- %s\n' % worksheet

        for source in worksheets[worksheet]:
            output += '  -- %s\n' % source

        output += '\n'

    output += '\n'*2
    return output

def filter_relations_for_datasource(datasource_name, relations):
    results = list()

    for r in relations:
        dsname = r['connection']
        if (datasource_name in dsname):
            results.append(r)

    retval = list({r['name']:r for r in results}.values())

    return retval

def format_datasources(datasources, relations):
    """Format datasources object for outfile."""
    output = '-- Datasources & Connections %s\n' % ('-'*(LINE_BIG-29))

    for source in datasources:
        ds_name = datasources[source]['datasource_name']

        output += '--DATA SOURCE %s\n' % datasources[source]['source_caption']
        output += '  -- Source name: %s\n' % ds_name
        output += '  -- Named connection source name: %s\n' % datasources[source]['source_name']
        output += '  -- Server: %s\n' % datasources[source]['server']
        output += '  -- Username: %s\n' % datasources[source]['user']
        output += '  -- Engine: %s\n' % datasources[source]['engine']
        output += '  -- Database: %s\n' % datasources[source]['db']
        output += '  -- Schema: %s\n' % datasources[source]['schema']
        output += '\n'*2

        output += format_relations(filter_relations_for_datasource(ds_name, relations), ds_name)

    return output


def format_relations(relations, dsname):
    """Format relations object for outfile."""
    output = f'  ------- relations for datasource {dsname}\n'

    for r in relations:
        output += '      -- RELATION %s %s\n' % (r['name'], '-'*(LINE_SMALL-4-len(r['name'])))
        output += '       -- Connection: %s\n' % r['connection']
        output += '       -- Name: %s\n' % r['name']
        output += '       -- Type: %s\n' % r['type']
        output += '       -- Table: %s\n' % r['table']
        output += '       -- Custom Query: %s\n' % r['table']
        output += r['query']
        output += '\n;%s' % ('\n'*3)

    return output


def convert(filename):
    """Process tableau to sql conversion."""
    twb = return_xml(filename)

    worksheets = parse_worksheets(twb.find('worksheets'))
    datasources = parse_datasources(twb.find('datasources'))
    relations = parse_relations(twb.findall('.//relation'))

    output = format_header(filename)
    output += format_worksheets(worksheets)
    output += format_datasources(datasources, relations)

    return output
