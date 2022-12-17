# -*- coding: utf-8 -*-

{
    'name': 'Channel Engine module',

    "author": "Huzaifa",
    'version': '0.1',
    'category': 'Services',
    'sequence': -1,
    'summary': 'Channel Engine Integration with odoo ',
    'description': "Module Integrates Channel Engine API with Odoo. ",
    'website': '',
    'images': [
    ],
    'depends': [
        
        'contacts',
        'stock',
        'sale_management'
	
    ],
    'data': [
        
       'security/ir.model.access.csv',
        'views/product.xml',
        'views/customer.xml',
        'views/order.xml',
        'views/api.xml',
        
    ],
    'demo': [
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'qweb': [
    ],
    'license': 'LGPL-3',
}
