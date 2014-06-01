# coding: utf-8
#
# Copyright 2014 The Oppia Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS-IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

'''Provides search services.'''

__author__ = 'Frederik Creemers'

from google.appengine.api import search as gae_search

import feconf

import numbers
import datetime


class SearchFailureError(Exception):
    def __init__(self, message, original_exception=None):
        super(SearchFailureError, self)
        self.original_exception = original_exception


def add_documents_to_index(documents, index, language=feconf.DEFAULT_LANGUAGE_CODE, retries=3):
    """Adds a document to an index.

    Args:
      - documents: a list of documents. Each document should be a dictionary.
        Every key in the document is a field name, and the corresponding value will be the field's value.
        If there is a key named 'id', its value will be used as the document's id.
      - index: the name f the index to insert the document into.
      - language: the language the document was written in.
      - retries: the number of times to retry inserting the documents.

    Returns:
      returns a list of document ids.
    """
    index = gae_search.Index(index)
    gae_docs = [_dict_to_search_document(d) for d in documents]

    try:
        results = index.put(gae_docs, deadline=5)
    except gae_search.PutError as e:
        result = e.results[0]
        if result.code == gae_search.OperationResult.TRANSIENT_ERROR and retries > 0:
            return add_documents_to_index(documents, index, language, retries-1)
        else:
            raise SearchFailureError(e.message, e)

    return [r.id for r in results]



def _dict_to_search_document(d):
    if not isinstance(d, dict):
        raise ValueError('document should be a dictionary')

    doc_id = None
    if 'id' in d:
        doc_id = d['id']

    fields = []

    for key, value in d.iteritems():
        if key == 'id':
            continue

        fields += _make_fields(key, value)

    doc = gae_search.Document(doc_id=doc_id, fields=fields)
    return doc


def _make_fields(key, value):
    if isinstance(value, list):
        return [_make_fields(key, v) for v in value]

    if isinstance(value, basestring):
        return [gae_search.TextField(name=key, value=value)]

    if isinstance(value, numbers.Number):
        return [gae_search.NumberField(name=key, value=value)]

    if isinstance(value, datetime.datetime) or isinstance(value, datetime.date):
        return [gae_search.DateField(name=key, value=value)]

    raise ValueError('Value for document field %s should be a (unicode) string, numeric type, datetime.date, ' \
                 'datetime.datetime or list of such types, got %s' % (key, type(value)))


def delete_documents_from_index(doc_ids, index, retries=3):
    """Deletes documents from an index

    Args:
      - documents: a list of document ids of documents to be deleted from the index.
      - index: the name f the index to delete the document from.
      - retries: the number of times to retry deleting the documents.

    Returns:
      returns True on success
    """
    index = gae_search.Index(index)
    try:
        index.delete(doc_ids, deadline=5)
        return True
    except gae_search.DeleteError as e:
        result = e.results[0]
        if result.code == gae_search.OperationResult.TRANSIENT_ERROR and retries > 0:
            return delete_documents_from_index(doc_ids, index, retries-1)
        else:
            raise SearchFailureError(e.message, e)


def search(query_string, index, cursor=gae_search.Cursor(), limit=20, ids_only=False, retries=3):
    """Searches for documents in an index

    Args:
      - query_string: the search query.
                      The syntax used is described here: https://developers.google.com/appengine/docs/python/search/query_strings
      - index: the name of the index to search.
      - cursor: a cursor, describing where to start searching. Leave blank to start at the beginning.
                This function returns a cursor, that you can use to retrieve the next 'page' of search results.
      - limit: the maximum number of documents to return.
      - ids_only: whether to only return document ids.
      - retries: the number of times to retry inserting the documents.

    Returns:
      returns a tuple with two elements:
        - a list of dictionaries representing search documents
        - a cursor that you can pass back in to get the next page of results.
    """
    options = gae_search.QueryOptions(limit=limit, cursor=cursor, ids_only=ids_only)
    query = gae_search.Query(query_string, options)
    index = gae_search.Index(index)

    try:
        results = index.search(query)
    except gae_search.Error as e:
        if retries > 0:
            return search(query_string, index, cursor, limit, ids_only, retries-1)

    return [_search_document_to_dict(doc) for doc in results.results], results.cursor


def _search_document_to_dict(doc):
    d = {'id': doc.doc_id}

    for field in doc.fields:
        d[field.name] = field.value

    return d
