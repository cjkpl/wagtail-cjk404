from wagtail.admin.ui.tables import Table


class SiteColorTable(Table):
    def __init__(self, *args, row_attr_func=None, **kwargs):
        self.row_attr_func = row_attr_func
        super().__init__(*args, **kwargs)

    def get_row_attrs(self, instance):
        attrs = super().get_row_attrs(instance)
        if callable(self.row_attr_func):
            extra = self.row_attr_func(instance) or {}
            attrs.update(extra)
        return attrs

