# Generated by Django 4.1.3 on 2022-11-12 13:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cjk404", "0002_pagenotfoundentry_fallback_redirect"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pagenotfoundentry",
            name="redirect_to_url",
            field=models.CharField(
                blank=True, max_length=400, null=True, verbose_name="Redirect to URL"
            ),
        ),
        migrations.AlterField(
            model_name="pagenotfoundentry",
            name="url",
            field=models.CharField(max_length=400, verbose_name="Redirect from URL"),
        ),
    ]
