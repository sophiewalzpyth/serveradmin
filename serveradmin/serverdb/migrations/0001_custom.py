# -*- coding: utf-8 -*-

from django.db import migrations


class Migration(migrations.Migration):
    operations = [
        migrations.RunSQL('CREATE EXTENSION pg_trgm'),
        migrations.RunSQL('CREATE EXTENSION btree_gist'),
        migrations.RunSQL(
            'ALTER TABLE project '
            'ADD CONSTRAINT project_project_id_check '
            "   CHECK (project_id ~ '^[a-z][a-z0-9_]*$'),"
            'ADD CONSTRAINT project_subdomain_check '
            "   CHECK (subdomain ~ '^[a-z][a-z0-9\\.\\-]*$'),"
        ),
        migrations.RunSQL(
            'ALTER TABLE segment '
            'ADD CONSTRAINT segment_segment_id_check '
            "   CHECK (segment_id ~ '^[a-z][a-z0-9_]*$')"
        ),
        migrations.RunSQL(
            'ALTER TABLE servertype '
            'ADD CONSTRAINT servertype_servertype_id_check '
            "   CHECK (servertype_id ~ '^[a-z][a-z0-9_]*$')"
        ),
        migrations.RunSQL(
            'ALTER TABLE attribute '
            'ADD CONSTRAINT attribute_attribute_id_check '
            "   CHECK (attribute_id ~ '^[a-z][a-z0-9_]*$')"
            'ADD CONSTRAINT attribute_multi_check '
            '   CHECK ('
            "       type NOT IN ('boolean', 'supernet') OR not multi"
            '   ),'
            'ADD CONSTRAINT attribute_readonly_check '
            '   CHECK ('
            "       type NOT IN ('reverse_hostname', 'supernet') OR readonly"
            '   ),'
            'ADD CONSTRAINT attribute_target_servertype_id_check '
            '   CHECK ('
            "       (type IN ('hostname', 'supernet')) = "
            '           (target_servertype_id IS NOT NULL)'
            '   ),'
            'ADD CONSTRAINT attribute_reversed_attribute_id_check '
            '   CHECK ('
            "       (type = 'reverse_hostname') = "
            '           (reversed_attribute_id IS NOT NULL)'
            '   )'
        ),
        migrations.RunSQL(
            'ALTER TABLE server '
            'ADD CONSTRAINT server_hostname_check '
            "   CHECK (hostname ~ '^[a-z][a-z0-9\\.\\-]*$'),"
            'ADD CONSTRAINT server_inter_ip_exclude '
            '   EXCLUDE USING gist ('
            '       intern_ip inet_ops WITH &&,'
            '       servertype_id WITH ='
            '   )'
            "   WHERE (servertype_id != 'loadbalancer')"
        ),
        migrations.RunSQL(
            'CREATE INDEX server_hostname_trgm '
            'ON server USING gin (hostname gin_trgm_ops)'
        ),
    ]
