"""Serveradmin - Servershell

Copyright (c) 2020 InnoGames GmbH
"""

import json
from distutils.util import strtobool
from itertools import islice

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import (
    ObjectDoesNotExist, PermissionDenied, ValidationError
)
from django.http import HttpResponse, HttpResponseRedirect, Http404, \
    JsonResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.html import mark_safe, escape as escape_html

from adminapi.datatype import DatatypeError
from adminapi.filters import Any, ContainedOnlyBy, filter_classes
from adminapi.parse import parse_query
from adminapi.request import json_encode_extra
from serveradmin.dataset import Query
from serveradmin.serverdb.models import (
    Servertype,
    Attribute,
    ServertypeAttribute,
    Server)
from serveradmin.serverdb.query_committer import commit_query
from serveradmin.servershell.helper.autocomplete import \
    attribute_value_startswith, attribute_startswith

MAX_DISTINGUISHED_VALUES = 50
NUM_SERVERS_DEFAULT = 25
AUTOCOMPLETE_LIMIT = 20


@login_required
def index(request):
    # If user clicks a link with shown attributes configured take that one
    shown_attributes = request.GET.getlist('shown_attributes[]')
    if not shown_attributes:
        if 'shown_attributes' in request.session:
            # The preferred settings of the user
            shown_attributes = request.session['shown_attributes']
        else:
            # Our default selection if the user visits the first time
            shown_attributes = list(Attribute.specials.keys())
            shown_attributes.remove('object_id')
            shown_attributes.append('state')
            shown_attributes.sort()

    request.session['shown_attributes'] = shown_attributes

    attributes = list(Attribute.objects.all())
    attributes.extend(Attribute.specials.values())
    attributes_json = list()
    for attribute in attributes:
        attributes_json.append({
            'attribute_id': attribute.attribute_id,
            'type': attribute.type,
            'multi': attribute.multi,
            'hovertext': attribute.hovertext,
            'help_link': attribute.help_link,
            'group': attribute.group,
            'regex': (
                # XXX: HTML5 input patterns do not support these
                None if not attribute.regexp else
                attribute.regexp.replace('\\A', '^').replace('\\Z', '$')
            ),
        })
    attributes_json.sort(key=lambda attr: attr['group'])

    return TemplateResponse(request, 'servershell/index.html', {
        'term': request.GET.get('term', request.session.get('term', '')),
        'shown_attributes': shown_attributes,
        'attributes': attributes_json,
        'offset': 0,
        'limit': request.session.get('limit', NUM_SERVERS_DEFAULT),
        'order_by': 'hostname',
        'command_history': json.dumps(
            request.session.get('command_history', [])),
        'filters': sorted([(f.__name__, f.__doc__) for f in filter_classes]),
        'autocomplete': request.session.get('autocomplete', True),
        'autoselect': request.session.get('autoselect', True),
    })


@login_required
def autocomplete(request):
    autocomplete_list = list()
    hostname = request.GET.get('hostname')
    attribute_id = request.GET.get('attribute')
    attribute_val = request.GET.get('value')

    if hostname:
        try:
            query = Server.objects.filter(hostname__startswith=hostname).only(
                'hostname').order_by('hostname')
            autocomplete_list = [server.hostname for server in
                                 query[:AUTOCOMPLETE_LIMIT]]
        except (DatatypeError, ValidationError):
            # If there is no valid query, just don't auto-complete
            pass

    if attribute_id:
        if attribute_val:
            autocomplete_list = attribute_value_startswith(attribute_id,
                                                           attribute_val,
                                                           AUTOCOMPLETE_LIMIT)
        else:
            autocomplete_list = attribute_startswith(attribute_id,
                                                     AUTOCOMPLETE_LIMIT)

    return HttpResponse(json.dumps({'autocomplete': autocomplete_list}),
                        content_type='application/x-json')


@login_required
def get_results(request):
    term = request.GET.get('term', '')
    shown_attributes = request.GET.getlist('shown_attributes[]',
                                           request.session['shown_attributes'])

    try:
        offset = int(request.GET.get('offset', '0'))
        limit = int(request.GET.get('limit', '0'))
    except ValueError:
        offset = 0
        limit = NUM_SERVERS_DEFAULT

    if 'order_by' in request.GET:
        order_by = [request.GET['order_by']]
    else:
        order_by = None

    try:

        # Query manipulates shown_attributes by adding object_id we want to
        # keep the original value to save settings ...
        restrict = shown_attributes.copy()
        if 'servertype' not in restrict:
            restrict.append('servertype')
        query = Query(parse_query(term), restrict, order_by)

        # TODO: Using len is terribly slow for large datasets because it has
        #  to query all objects but we cannot use count which is available on
        #  Django QuerySet
        num_servers = len(query)
    except (DatatypeError, ObjectDoesNotExist, ValidationError) as error:
        return HttpResponse(json.dumps({
            'status': 'error',
            'message': str(error)
        }))

    servers = list(islice(query, offset, offset + limit))

    # Save settings across requests and tabs
    request.session['term'] = term
    request.session['limit'] = limit
    request.session['shown_attributes'] = shown_attributes

    # Add information about available, editable attributes on servertypes
    servertype_ids = {s['servertype'] for s in servers}

    default_editable = list(Attribute.specials)
    default_editable.remove('object_id')

    editable_attributes = dict()
    for servertype_id in servertype_ids:
        editable_attributes[servertype_id] = default_editable.copy()
    for sa in ServertypeAttribute.objects.filter(
            servertype_id__in=servertype_ids,
            attribute_id__in=shown_attributes,
            related_via_attribute_id__isnull=True,
            attribute__readonly=False,
    ):
        editable_attributes[sa.servertype_id].append(sa.attribute_id)

    return HttpResponse(json.dumps({
        'status': 'success',
        'understood': repr(query),
        'servers': servers,
        'num_servers': num_servers,
        'editable_attributes': editable_attributes,
    }, default=json_encode_extra), content_type='application/x-json')


@login_required
def export(request):
    term = request.GET.get('term', '')
    try:
        query = Query(parse_query(term), ['hostname'])
    except (DatatypeError, ObjectDoesNotExist, ValidationError) as error:
        return HttpResponse(str(error), status=400)

    hostnames = ' '.join(server['hostname'] for server in query)
    return HttpResponse(hostnames, content_type='text/plain')


@login_required
def inspect(request):
    server = Query({'object_id': request.GET['object_id']}, None).get()
    return _edit(request, server, template='inspect')


@login_required
def edit(request):
    if 'object_id' in request.GET:
        server = Query({'object_id': request.GET['object_id']}, None).get()
    else:
        servertype = request.POST.get('attr_servertype')
        if not Servertype.objects.filter(pk=servertype).exists():
            raise Http404('Servertype {} does not exist'.format(servertype))
        server = Query().new_object(servertype)

    return _edit(request, server, True)


def _edit(request, server, edit_mode=False, template='edit'):  # NOQA: C901
    invalid_attrs = set()
    if edit_mode and request.POST:
        attribute_lookup = {a.pk: a for a in Attribute.objects.filter(
            attribute_id__in=(k[len('attr_'):] for k in request.POST.keys())
        )}
        attribute_lookup.update(Attribute.specials)
        for key, value in request.POST.items():
            if not key.startswith('attr_'):
                continue
            attribute_id = key[len('attr_'):]
            attribute = attribute_lookup[attribute_id]
            value = value.strip()
            if attribute.multi:
                values = [v.strip() for v in value.splitlines()]
                try:
                    value = attribute.from_str(values)
                except ValidationError:
                    invalid_attrs.add(attribute_id)
                    value = set(values)
            elif value == '':
                value = None
            else:
                try:
                    value = attribute.from_str(value)
                except ValidationError:
                    invalid_attrs.add(attribute_id)

            server[attribute_id] = value

        if not invalid_attrs:
            if server.object_id:
                action = 'edited'
                created = []
                changed = [server._serialize_changes()]
            else:
                action = 'created'
                created = [server]
                changed = []

            try:
                commit_obj = commit_query(created, changed, user=request.user)
            except (PermissionDenied, ValidationError) as err:
                messages.error(request, str(err))
            else:
                messages.success(request, 'Server successfully ' + action)
                if action == 'created':
                    server = commit_obj.created[0]

                url = '{0}?object_id={1}'.format(
                    reverse('servershell_inspect'),
                    server.object_id,
                )
                return HttpResponseRedirect(url)

        if invalid_attrs:
            messages.error(request, 'Attributes contains invalid values')

    servertype = Servertype.objects.get(pk=server['servertype'])
    attribute_lookup = {a.pk: a for a in Attribute.objects.filter(
        attribute_id__in=(server.keys())
    )}
    attribute_lookup.update(Attribute.specials)
    servertype_attributes = {sa.attribute_id: sa for sa in (
        ServertypeAttribute.objects.filter(servertype_id=server['servertype'])
    )}

    fields = []
    fields_set = set()
    for key, value in server.items():
        if (
                key == 'object_id' or
                key == 'intern_ip' and servertype.ip_addr_type == 'null'
        ):
            continue

        attribute = attribute_lookup[key]
        servertype_attribute = servertype_attributes.get(key)
        if servertype_attribute and servertype_attribute.related_via_attribute:
            continue

        fields_set.add(key)
        fields.append({
            'key': key,
            'value': value,
            'type': attribute.type,
            'multi': attribute.multi,
            'required': (
                    servertype_attribute and servertype_attribute.required or
                    key in Attribute.specials.keys()
            ),
            'regexp_display': _prepare_regexp_html(attribute.regexp),
            'regexp': (
                # XXX: HTML5 input patterns do not support these
                None if not attribute.regexp else
                attribute.regexp.replace('\\A', '^').replace('\\Z', '$')
            ),
            'default': (
                    servertype_attribute and servertype_attribute.default_value
            ),
            'readonly': attribute.readonly,
            'error': key in invalid_attrs,
            'hovertext': attribute.hovertext,
        })

    fields.sort(key=lambda k: (not k['required'], k['key']))
    return TemplateResponse(request, 'servershell/{}.html'.format(template), {
        'object_id': server.object_id,
        'hostname': server['hostname'],
        'fields': fields,
        'is_ajax': request.is_ajax(),
        'base_template': 'empty.html' if request.is_ajax() else 'base.html',
        'link': request.get_full_path(),
    })


@login_required
def commit(request):
    try:
        commit_obj = json.loads(request.POST['commit'])
    except (KeyError, ValueError) as error:
        result = {
            'status': 'error',
            'message': str(error),
        }
    else:
        changed = []
        if 'changes' in commit_obj:
            for key, value in commit_obj['changes'].items():
                value['object_id'] = int(key)
                changed.append(value)

        deleted = commit_obj.get('deleted', [])
        user = request.user

        try:
            commit_query(changed=changed, deleted=deleted, user=user)
        except (PermissionDenied, ValidationError) as error:
            result = {
                'status': 'error',
                'message': str(error),
            }
        else:
            result = {'status': 'success'}

    return HttpResponse(json.dumps(result), content_type='application/x-json')


@login_required
def new_object(request):
    servertype = request.GET.get('servertype')

    try:
        new_object = Query().new_object(servertype)
    except Servertype.DoesNotExist:
        messages.error(request,
                       'The servertype {} does not exist!'.format(servertype))
        return redirect('servershell_index')

    return _edit(request, new_object)


@login_required
def clone_object(request):
    try:
        old_object = Query(
            {'object_id': request.GET.get('object_id')},
            list(Attribute.specials) + list(
                Attribute.objects.filter(clone=True)
                    .values_list('attribute_id', flat=True)
            ),
        ).get()
    except ValidationError as e:
        messages.error(request, e.message)
        return redirect('servershell_index')

    new_object = Query().new_object(old_object['servertype'])
    for attribute_id, value in old_object.items():
        new_object[attribute_id] = value

    return _edit(request, new_object)


@login_required
def choose_ip_addr(request):
    if 'network' not in request.GET:
        servers = list(
            Query({'servertype': 'route_network'}, ['hostname', 'intern_ip'],
                  ['hostname']))

        return TemplateResponse(request, 'servershell/choose_ip_addr.html',
                                {'servers': servers})

    network = request.GET['network']
    servers = list(Query(
        {
            'servertype': Any(*(
                s.servertype_id
                for s in Servertype.objects.filter(ip_addr_type='network')
            )),
            'intern_ip': ContainedOnlyBy(network),
        },
        ['hostname', 'intern_ip'],
        ['hostname'],
    ))

    if servers:
        return TemplateResponse(request, 'servershell/choose_ip_addr.html',
                                {'servers': servers})

    network_query = Query({'intern_ip': network}, ['intern_ip'])

    return TemplateResponse(request, 'servershell/choose_ip_addr.html', {
        'ip_addrs': islice(network_query.get_free_ip_addrs(), 1000)})


@login_required
def settings(request):
    """Save search settings

    Save settings of the Servershell to session.

    :param request:
    :return:
    """
    request.session['autocomplete'] = bool(strtobool(
        request.GET.get('autocomplete', 'true')))
    request.session['autoselect'] = bool(strtobool(
        request.GET.get('autoselect', 'true')))

    return JsonResponse({'status': 'ok'})


def _prepare_regexp_html(regexp):
    """Return HTML for a given regexp. Includes wordbreaks."""
    if not regexp:
        return ''
    else:
        regexp_html = (escape_html(regexp).replace('|', '|&#8203;')
                       .replace(']', ']&#8203;').replace(')', ')&#8203;'))
        return mark_safe(regexp_html)
