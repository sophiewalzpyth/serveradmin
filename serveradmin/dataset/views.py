from django.http import Http404
from django.template.response import TemplateResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages

from serveradmin.dataset.base import lookups
from serveradmin.dataset.models import ServerType

@login_required
def servertypes(request):
    return TemplateResponse(request, 'dataset/servertypes.html', {
        'servertypes': ServerType.objects.order_by('name')
    })

@login_required
def view_servertype(request, servertype_name):
    try:
        servertype = lookups.stype_names[servertype_name]
    except KeyError:
        raise Http404

    stype_attributes = []
    for attr in servertype.attributes:
        stype_attr = lookups.stype_attrs[(servertype.name, attr.name)]
        attr_obj = lookups.attr_ids[stype_attr.attribute_id]
        stype_attributes.append({
            'name': attr_obj.name,
            'type': attr_obj.type,
            'multi': attr_obj.multi,
            'required': stype_attr.required,
            'regexp': stype_attr.regexp.pattern if stype_attr.regexp else None,
            'default': stype_attr.default
        })

    return TemplateResponse(request, 'dataset/view_servertype.html', {
        'servertype': servertype,
        'attributes': stype_attributes
    })

def delete_servertype(request, servertype_name):
    stype = get_object_or_404(ServerType, name=servertype_name)
    if request.method == 'POST':
        if 'confirm' in request.POST:
            stype.delete()
            messages.success(request, u'Servertype deleted.')
        else:
            msg = u'Please confirm the usage of weapons of mass destruction.'
            messages.error(request, msg)
            return redirect('dataset_view_servertype', servertype_name)
    return redirect('dataset_servertypes')
