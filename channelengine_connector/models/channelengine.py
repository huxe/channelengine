import requests
import json
from odoo.exceptions import UserError
from odoo import models, fields, api, exceptions


class Credential(models.Model):
    _name = "channelengine.credential"

    name=fields.Char(string="Name",required=True)
    channel_engine_url=fields.Char(string="Channel Engine URL",required=True)
    api_key=fields.Char(string="Api Key",required=True)
    isActive=fields.Boolean(string="Crone Job Active", default=False)
    shipping_product = fields.Many2one('product.product', string='Shippping Product')

    def sync_All(self):
        pass

class inheritProductCategory(models.Model):
    _inherit="product.category"
    
    category_sync=fields.Boolean(string="Category Sync")
    category_code=fields.Char(string="Grand Parent Internal Reference")
    ean_number=fields.Char(string="Ean")

class inheritProductTemplate(models.Model):
    _inherit="product.template"
    
    product_template_sync=fields.Boolean(string="Product Template Sync")
    product_template_default_code=fields.Char(string="Parent Internal Reference")
    product_images = fields.One2many('ir.attachment', 'product_template_id', string='Product Images (Not more than 10)')
    ean_number=fields.Char(string="Ean")

class inheritProductTemplate(models.Model):
    _inherit="ir.attachment"
    
    product_product_id=fields.Many2one(string="Child Product Id", comodel_name='product.product')
    product_template_id=fields.Many2one(string="Parent Product Id", comodel_name='product.template')

class inh_Product(models.Model):
    _inherit="product.product"

    product_sync=fields.Boolean(string="Product Variant Sync")
    ean_number=fields.Char(string="Ean")
    product_images = fields.One2many('ir.attachment', 'product_product_id', string='Product Images (Not more than 10)')
    # parent_product=fields.Many2one('product.template', string="Parent Product")

    #overriding write for archiving products on channel engine
    def write(self, values):
        res = super(inh_Product, self).write(values)
        if 'active' in values:
            products_archive_list = []
            for record in self:
                products_archive_list.append(record.default_code)
            
            if products_archive_list:
                api_info=self.env['channelengine.credential'].search([("isActive",'=',True)])
                cred=api_info[0]
                url=cred.channel_engine_url+"/products/bulkdelete?apikey="+cred.api_key
                payload = json.dumps(products_archive_list)
                headers = {
                    'Content-Type': 'application/json'
                }

                response = requests.request("POST", url, headers=headers, data=payload)
        return res

    def sync_odoo_prod(self):
        #tv-11 -> tv-12
        categories=self.env['product.category'].search([('category_sync','=',False)])
        self.create_grandparent_product(categories)
        prods_template=self.env['product.template'].search([('product_template_sync','=',False)])
        self.create_parent_product(prods_template)
        prods=self.env['product.product'].search([('product_sync','=',False)])
        self.create_child_product(prods)
    
    def create_grandparent_product(self, categories):
        product_create=[]
        for categ in categories:
            if not categ.category_sync and categ.category_code:
                product_create.append(
                    {
                        "Name": categ.display_name,
                        "MerchantProductNo": categ.category_code,
                        "Stock": 1,
                        # "ExtraData": [
                        #     {
                        #         "Type": "Parent",
                        #         "IsPublic": False,
                        #     }
                        # ],
                        "Price": 1,
                        "Ean": categ.ean_number,
                        "PurchasePrice": 1,
                    }
                )
                categ.category_sync = True

        if product_create:
            api_info=self.env['channelengine.credential'].search([("isActive",'=',True)])
            cred=api_info[0]
            url=cred.channel_engine_url+"/products?apikey="+cred.api_key
            payload = json.dumps(product_create)
            headers = {
                'Content-Type': 'application/json'
            }

            response = requests.request("POST", url, headers=headers, data=payload)
            # raise UserError(response.text)
                

    def create_parent_product(self, prods_template):
        # url = "https://vandewaetere-trading-bv-dev.channelengine.net/api/v2/products?apikey=b536e286af2ac6436fdc5c926315d822166cd64c"
        product_create=[]
        # api_info=self.env['channelengine.credential'].search([("isActive",'=',True)])
        # cred=api_info[0]
        for product in prods_template:
            #Asir
            if not product.product_template_sync and product.product_template_default_code:
                if '/' in product.categ_id.display_name:
                    category_trail = product.categ_id.display_name.replace('/','>')
                else:
                    category_trail = product.categ_id.display_name

                # product_create.append(
                #     {
                #         "Name": product.name,
                #         "MerchantProductNo": product.product_template_default_code,
                #         "ParentMerchantProductNo2": product.categ_id.category_code,
                #         "ParentMerchantProductNo": "",
                #         "Stock": int(product.qty_available),
                #         # "ExtraData": [
                #         #     {
                #         #         "Type": "Parent",
                #         #         "IsPublic": False,
                #         #     }
                #         # ],
                #         "Price": product.list_price,
                #         "Ean": product.ean_number,
                #         "PurchasePrice": product.standard_price,
                #         "CategoryTrail": category_trail
                #     }
                # )

                if product.product_images:
                    first_image = {}
                    product_dict = {}
                    img_counter=1
                    for img_recs in product.product_images:
                        first_image = img_recs
                        break
                    for img_recs in product.product_images:
                        if img_counter == 10:
                            break
                        if img_recs.id == first_image.id:
                            #Replace localhost Url
                            product_dict.update({"ImageUrl":"http://localhost:8069"+img_recs.local_url})
                        else:
                            #Replace localhost Url
                            product_dict.update({"ExtraImageUrl"+img_counter:"http://localhost:8069"+img_recs.local_url})
                            img_counter+=1
                    product_dict.update({
                            "Name": product.name,
                            "MerchantProductNo": product.product_template_default_code,
                            "ParentMerchantProductNo2": product.categ_id.category_code,
                            "ParentMerchantProductNo": "",
                            "Stock": int(product.qty_available),
                            # "ExtraData": [
                            #     {
                            #         "Type": "Parent",
                            #         "IsPublic": False,
                            #     }
                            # ],
                            "Price": product.list_price,
                            "Ean": product.ean_number,
                            "PurchasePrice": product.standard_price,
                            "CategoryTrail": category_trail
                        })
                    product_create.append(product_dict)
                else:
                    product_create.append(
                        {
                            "Name": product.name,
                            "MerchantProductNo": product.product_template_default_code,
                            "ParentMerchantProductNo2": product.categ_id.category_code,
                            "ParentMerchantProductNo": "",
                            "Stock": int(product.qty_available),
                            # "ExtraData": [
                            #     {
                            #         "Type": "Parent",
                            #         "IsPublic": False,
                            #     }
                            # ],
                            "Price": product.list_price,
                            "Ean": product.ean_number,
                            "PurchasePrice": product.standard_price,
                            "CategoryTrail": category_trail
                        }
                    )
                    
                product.product_template_sync = True

        if product_create:
            api_info=self.env['channelengine.credential'].search([("isActive",'=',True)])
            cred=api_info[0]
            url=cred.channel_engine_url+"/products?apikey="+cred.api_key
            payload = json.dumps(product_create)
            headers = {
                'Content-Type': 'application/json'
            }

            response = requests.request("POST", url, headers=headers, data=payload)
            # raise UserError(response.text)

    def create_child_product(self, prods):
        # url = "https://vandewaetere-trading-bv-dev.channelengine.net/api/v2/products?apikey=b536e286af2ac6436fdc5c926315d822166cd64c"
        product_create=[]
        # api_info=self.env['channelengine.credential'].search([("isActive",'=',True)])
        # cred=api_info[0]
        for product in prods:
            #Asir
            if not product.product_sync and product.default_code:
                color_val = False
                size_val = False 
                if product.product_template_variant_value_ids:
                    for variant in product.product_template_variant_value_ids:
                        if variant.attribute_id.name == 'Color':
                            color_val = variant.name
                        elif variant.attribute_id.name == 'Size':
                            size_val = variant.name

                if '/' in product.categ_id.display_name:
                    category_trail = product.categ_id.display_name.replace('/','>')
                else:
                    category_trail = product.categ_id.display_name

                # raise UserError(product.product_tmpl_id.product_template_default_code)
                # product_create.append(
                #     {
                #         "Name": product.display_name,
                #         "ParentMerchantProductNo": product.product_tmpl_id.product_template_default_code if product.product_tmpl_id.product_template_default_code else False,
                #         "ParentMerchantProductNo2": "",
                #         "MerchantProductNo": product.default_code,
                #         "Size": size_val or "",
                #         "Color": color_val or "",
                #         # "ExtraData": [
                #         #     {
                #         #         "Type": "Child",
                #         #         "IsPublic": True,
                #         #     }
                #         # ],
                #         "Stock": int(product.qty_available),
                #         "Price": product.list_price,
                #         "Ean": product.ean_number,
                #         "PurchasePrice": product.standard_price,
                #         "CategoryTrail": category_trail
                #     }
                # )

                if product.product_images:
                    first_image = {}
                    product_dict = {}
                    img_counter=1
                    for img_recs in product.product_images:
                        first_image = img_recs
                        break
                    for img_recs in product.product_images:
                        if img_counter == 10:
                            break
                        if img_recs.id == first_image.id:
                            #Replace localhost Url
                            product_dict.update({"ImageUrl":"http://localhost:8069"+img_recs.local_url})
                        else:
                            #Replace localhost Url
                            product_dict.update({"ExtraImageUrl"+img_counter:"http://localhost:8069"+img_recs.local_url})
                            img_counter+=1
                    product_dict.update({
                            "Name": product.display_name,
                            "ParentMerchantProductNo": product.product_tmpl_id.product_template_default_code if product.product_tmpl_id.product_template_default_code else "",
                            "ParentMerchantProductNo2": "",
                            "MerchantProductNo": product.default_code,
                            "Size": size_val or "",
                            "Color": color_val or "",
                            # "ExtraData": [
                            #     {
                            #         "Type": "Child",
                            #         "IsPublic": True,
                            #     }
                            # ],
                            "Stock": int(product.qty_available),
                            "Price": product.list_price,
                            "Ean": product.ean_number,
                            "PurchasePrice": product.standard_price,
                            "CategoryTrail": category_trail
                        })
                    product_create.append(product_dict)
                else:
                    product_create.append(
                        {
                            "Name": product.display_name,
                            "ParentMerchantProductNo": product.product_tmpl_id.product_template_default_code if product.product_tmpl_id.product_template_default_code else False,
                            "ParentMerchantProductNo2": "",
                            "MerchantProductNo": product.default_code,
                            "Size": size_val or "",
                            "Color": color_val or "",
                            # "ExtraData": [
                            #     {
                            #         "Type": "Child",
                            #         "IsPublic": True,
                            #     }
                            # ],
                            "Stock": int(product.qty_available),
                            "Price": product.list_price,
                            "Ean": product.ean_number,
                            "PurchasePrice": product.standard_price,
                            "CategoryTrail": category_trail
                        }
                    )

                product.product_sync = True

        api_info=self.env['channelengine.credential'].search([("isActive",'=',True)])
        cred=api_info[0]
        url=cred.channel_engine_url+"/products?apikey="+cred.api_key
        payload = json.dumps(product_create)
        headers = {
            'Content-Type': 'application/json'
        }

        response = requests.request("POST", url, headers=headers, data=payload)
        # raise UserError(response.text)

    
    def main_sync(self):
        prods_template=self.env['product.template'].search([('product_template_sync','=',True)])
        self.parent_product_stock_sync(prods_template)
        prods=self.env['product.product'].search([('product_sync','=',True)])
        prods.product_stock_sync()

    def parent_product_stock_sync(self, prods_template):    
        api_info=self.env['channelengine.credential'].search([("isActive",'=',True)])
        cred=api_info[0]
        url=cred.channel_engine_url+"/products?apikey="+cred.api_key
        payload = {
                    "PropertiesToUpdate": [
                    "Stock",
                    "Name",
                    "Price",
                    "PurchasePrice"
                    ],
                    "MerchantProductRequestModels": [
                    ]
                }
        for product in prods_template:
            if product.product_template_sync and product.product_template_default_code:
                product_dict = {
                    "MerchantProductNo": product.product_template_default_code,
                    "Stock": int(product.qty_available),
                    "Name": product.name,
                    "Price": product.list_price,
                    "PurchasePrice": product.standard_price
                }
                payload["MerchantProductRequestModels"].append(product_dict)

        headers = {
            'Content-Type': 'application/json'
        }
        json_payload = json.dumps(payload)
        response = requests.request("PATCH", url, headers=headers, data=json_payload)
        # raise UserError(str(response.text))
    
    def product_stock_sync(self):    
        api_info=self.env['channelengine.credential'].search([("isActive",'=',True)])
        cred=api_info[0]
        url=cred.channel_engine_url+"/products?apikey="+cred.api_key
        payload = {
                    "PropertiesToUpdate": [
                    "Stock",
                    "Name",
                    "Price",
                    "PurchasePrice"
                    ],
                    "MerchantProductRequestModels": [
                    ]
                }
        for product in self:
            if product.product_sync and product.default_code:
                product_dict = {
                    "MerchantProductNo": product.default_code,
                    "Stock": int(product.qty_available),
                    "Name": product.name,
                    "Price": product.list_price,
                    "PurchasePrice": product.standard_price
                }
                payload["MerchantProductRequestModels"].append(product_dict)

        headers = {
            'Content-Type': 'application/json'
        }
        json_payload = json.dumps(payload)
        response = requests.request("PATCH", url, headers=headers, data=json_payload)
        # raise UserError(str(response.text))

                


                
                    

 



                    
                    
                
        
    
                    
                
        
      

            



