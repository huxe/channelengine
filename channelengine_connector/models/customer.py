import requests
import json
from datetime import datetime
from odoo.exceptions import UserError
from odoo import models, fields, api, exceptions, _


class inheritedDeliveries(models.Model):
    _inherit="stock.picking"
    shipment_method=fields.Selection([('Briefpost', 'Briefpost'), ('DHL', 'DHL'),('dhlforyou', 'DHL FOR YOU'),('DPD', 'DPD'),('postNL', 'postNL'),('UPS', 'UPS'),('Other', 'Other')])

    tracking_code=fields.Char(string="Tracking code")
    return_tracking_code=fields.Char(string="Return Tracking code")
    tracking_url=fields.Char(string="Tracking URL")
    shipment_status=fields.Char(string="Shipment Information")
    return_status=fields.Char(string="Return Information")
    merchant_return_number=fields.Char(string="Merchant Return Number")
    channelengine_return_id=fields.Char(string="Return ID")
    return_reason = fields.Selection(selection=[
            ('PRODUCT_DEFECT', 'PRODUCT_DEFECT'),
            ('PRODUCT_UNSATISFACTORY', 'PRODUCT_UNSATISFACTORY'),
            ('WRONG_PRODUCT', 'WRONG_PRODUCT'),
            ('TOO_MANY_PRODUCTS', 'TOO_MANY_PRODUCTS'),
            ('REFUSED', 'REFUSED'),
            ('REFUSED_DAMAGED', 'REFUSED_DAMAGED'),
            ('WRONG_ADDRESS', 'WRONG_ADDRESS'),
            ('NOT_COLLECTED', 'NOT_COLLECTED'),
            ('WRONG_SIZE', 'WRONG_SIZE'),
            ('OTHER', 'OTHER'),
        ], string='Return Reason')

    def create_return_odoo(self):
        api_info=self.env['channelengine.credential'].search([("isActive",'=',True)])
        cred=api_info[0]
        url=cred.channel_engine_url+"/returns?apikey="+cred.api_key+"&statuses=IN_PROGRESS"

        response = requests.request("GET", url, headers={}, data={})

        dictt=response.json()

        ContentData = dictt['Content']

        for data in ContentData:
            #check existing sale order
            existing_sale_order = self.env['sale.order'].search([('channelengine_merchantOrderNo','=',data['MerchantOrderNo'])])
            if existing_sale_order:
                #check existing return in odoo
                existing_return = self.env['stock.picking'].search([('sale_id.channelengine_merchantOrderNo','=',data['MerchantOrderNo']),('picking_type_code','=','incoming')])
                if not existing_return:
                    returnLines=[]
                    for line in data['Lines']:
                        prod = self.env['product.product'].search([('default_code','=',line['MerchantProductNo'])])
                        if prod:
                        # product_name = self.env['product.product'].search([('default_code','=',line['MerchantProductNo'])]).display_name
                        # raise UserError(prod.id)
                            returnLines.append((0,0,{
                                # 'name': prod.display_name,
                                # 'product_id':prod.id,
                                # 'product_uom_qty':line['Quantity'],
                                # 'product_uom_id':1,
                                # 'location_id':5,
                                # 'location_dest_id':8,
                                # 'state':'draft'
                                'name':prod.display_name or '',
                                'product_id':prod.id,
                                'product_uom':prod.uom_id.id,
                                'product_uom_qty':line['Quantity'],
                                'location_id':5,
                                'location_dest_id':8,
                                'state':'draft',
                            }))
                    # raise UserError(str(returnLines))
                    existing_sale_order.write({
                        'channelengine_orderStatus': 'RETURNED'
                    })
                    # raise UserError(str(sale_order))
                    pickingID=self.env['stock.picking'].sudo().create({
                        # 'name':self.env['ir.sequence'].next_by_code('return_code'),
                        'picking_type_id':6,
                        'partner_id': existing_sale_order.partner_shipping_id.id,
                        'location_id':5,
                        'location_dest_id':8,
                        'sale_id': existing_sale_order.id,
                        'origin': 'Return of '+existing_sale_order.name,
                        'move_lines':returnLines,
                        # 'move_line_ids_without_package':returnLines,
                        'state':'draft',
                        'return_status': 'Created from Shipping Engine!',
                        'channelengine_return_id': data['Id'],
                        'merchant_return_number': data['MerchantReturnNo'],
                        'return_reason': data['Reason']
                    })


    def sync_returns_from_shipping_engine(self):
        self.create_return_odoo()
    
    def receive_return(self):
        api_info=self.env['channelengine.credential'].search([("isActive",'=',True)])
        cred=api_info[0]
        if self.channelengine_return_id:
            line_list = []
            for line in self.move_ids_without_package:
                if line.product_id.id != cred.shipping_product.id:
                    line_list.append({
                        'MerchantProductNo': line.product_id.default_code,
                        'AcceptedQuantity': int(line.quantity_done)
                    })

            url=cred.channel_engine_url+"/returns?apikey="+cred.api_key

            payload = json.dumps(
                {
                    "ReturnId": self.channelengine_return_id,
                    "Lines": line_list,
                }
            )

            headers = {
                'Content-Type': 'application/json'
            }

            response = requests.request("PUT", url, headers=headers, data=payload)
            resjson=response.json()
            if response.status_code == 200:
                self.shipment_status = 'RECEIVED'
            else:
                self.shipment_status =  resjson['Message']
    
    def create_return_channelengine(self):
        api_info=self.env['channelengine.credential'].search([("isActive",'=',True)])
        cred=api_info[0]
        line_list = []
        for line in self.move_ids_without_package:
            if line.quantity_done > 0:
                if line.product_id.id != cred.shipping_product.id:
                    line_list.append({
                        'MerchantProductNo': line.product_id.default_code,
                        'Quantity': int(line.quantity_done)
                    })

        if line_list:
            url=cred.channel_engine_url+"/returns/merchant?apikey="+cred.api_key

            payload = json.dumps(
                {
                    "MerchantOrderNo": self.sale_id.channelengine_merchantOrderNo,
                    "MerchantReturnNo": self.merchant_return_number,
                    "Lines": line_list,
                    "ReturnDate": str(self.scheduled_date),
                    "Reason": self.return_reason
                }
            )

            headers = {
                'Content-Type': 'application/json'
            }

            response = requests.request("POST", url, headers=headers, data=payload)
            resjson=response.json()
            if response.status_code == 201:
                self.sale_id.channelengine_orderStatus = 'RETURNED'
                self.return_status = resjson['Message']
            else:
                self.return_status =  resjson['Message']

            #attach return Id
            url=cred.channel_engine_url+"/returns?apikey="+cred.api_key+"&merchantOrderNos="+self.sale_id.channelengine_merchantOrderNo
            response = requests.request("GET", url, headers={}, data={})
            dictt=response.json()
            ContentData = dictt['Content']
            for data in ContentData:
                self.channelengine_return_id = data['Id']
            

    def button_validate(self):
        res = super(inheritedDeliveries, self).button_validate()
        runApi = False
        for line in self.move_ids_without_package:
            if line.quantity_done > 0:
                runApi = True
                break
            
        if runApi:
            if self.sale_id and self.picking_type_code == 'outgoing':
                self.create_shipment()
            elif self.sale_id and self.channelengine_return_id and self.picking_type_code == 'incoming':
                self.receive_return()
            elif self.sale_id and not self.channelengine_return_id and self.picking_type_code == 'incoming':
                if self.merchant_return_number:
                    self.create_return_channelengine()
                else:
                    raise UserError('Please enter Merchant Return Number')
        return res

    def create_shipment(self):
        #checking shipment first
        api_info=self.env['channelengine.credential'].search([("isActive",'=',True)])
        cred=api_info[0]
        url=cred.channel_engine_url+"/shipments/merchant?apikey="+cred.api_key+"&merchantOrderNos="+self.sale_id.channelengine_merchantOrderNo
        response = requests.request("GET", url, headers={}, data={})
        dictt=response.json()
        runApi = True
        if dictt['TotalCount'] > 0:
            runApi = False

        if runApi:
            line_list = []
            for line in self.move_ids_without_package:
                if line.product_id.id != cred.shipping_product.id:
                    line_list.append({
                        'MerchantProductNo': line.product_id.default_code,
                        'Quantity': int(line.quantity_done)
                    })
                
            for delivery in self:
                url=cred.channel_engine_url+"/shipments?apikey="+cred.api_key
                msno=delivery.name+'OdooTesting'
                

                payload = json.dumps(
                    {
                        "MerchantShipmentNo": msno,
                        "MerchantOrderNo":delivery.sale_id.channelengine_merchantOrderNo,
                        "Lines": line_list,
                        "TrackTraceNo":delivery.tracking_code,
                        "TrackTraceUrl":delivery.tracking_url,
                        "ReturnTrackTraceNo":delivery.return_tracking_code,
                        "Method":delivery.shipment_method,
                        "ShippedFromCountryCode":delivery.partner_id.country_id.code,
                        "ShipmentDate":str(delivery.scheduled_date) 
                    }
                )

                headers = {
                    'Content-Type': 'application/json'
                }

                response = requests.request("POST", url, headers=headers, data=payload)
                resjson=response.json()
                if response.status_code == 201:
                    delivery.sale_id.channelengine_orderStatus = 'SHIPPED'
                    delivery.shipment_status = resjson['Message']
                else:
                    delivery.shipment_status =  resjson['Message']



class inheritedSales(models.Model):
    _inherit="sale.order"
    
    channelengine_orderId=fields.Integer(string="ID")
    channelengine_merchantOrderNo=fields.Char(string="Merchant Order No")
    channelengine_orderStatus=fields.Char(string="Order Status")
    channelengine_merchantCancellationNo=fields.Char(string="Merchant Cancellation No")
    channelengine_cancellationReason=fields.Char(string="Order Cancellation Reason")

    def action_cancel(self):
        res = super(inheritedSales, self).action_cancel()
        if self.channelengine_orderStatus not in ['SHIPPED','RETURNED'] and self.channelengine_merchantOrderNo and self.channelengine_merchantCancellationNo:
            self.cancel_order()
            return res
        elif not self.channelengine_cancellationReason:
            raise UserError('Cancellation Reason is missing')
        elif not self.channelengine_merchantOrderNo:
            raise UserError('Merchant Order No is missing')
        elif not self.channelengine_merchantCancellationNo:
            raise UserError('Merchant Cancellation Number is Missing')
        else:
            raise UserError('You cannot cancel this Order')
    
    def cancel_order(self):
        api_info=self.env['channelengine.credential'].search([("isActive",'=',True)])
        cred=api_info[0]
        url=cred.channel_engine_url+"/cancellations?apikey="+cred.api_key
        line_list = []
        for line in self.order_line:
            if line.product_id.id != cred.shipping_product.id:
                line_list.append({
                    'MerchantProductNo': line.product_id.default_code,
                    'Quantity': int(line.product_uom_qty)
                })
        payload = json.dumps(
            {
                "MerchantCancellationNo": self.channelengine_merchantCancellationNo,
                "MerchantOrderNo": self.channelengine_merchantOrderNo,
                "Lines": line_list,
                "Reason": self.channelengine_cancellationReason,
                # "ReasonCode": "NOT_IN_STOCK"
            }
        )

        headers = {
            'Content-Type': 'application/json'
        }

        response = requests.request("POST", url, headers=headers, data=payload)
        # raise UserError(str(response.text))
        if response.status_code == 201:
            self.channelengine_orderStatus = 'CANCELED'

    def action_confirm(self):
        res = super(inheritedSales, self).action_confirm()
        self.acknowledge_orders()
        return res

    def acknowledge_orders(self): 
        api_info=self.env['channelengine.credential'].search([("isActive",'=',True)])
        cred=api_info[0]
        url=cred.channel_engine_url+"/orders?apikey="+cred.api_key

        response = requests.request("GET", url, headers={}, data={})

        dictt=response.json()

        ContentData = dictt['Content']
        
        for data in ContentData:
            sale_order=self.env["sale.order"].search([('channelengine_orderId', '=',data['Id'])])
            if data['Status']=='NEW':
             
                url=cred.channel_engine_url+"/orders/acknowledge?apikey="+cred.api_key
               
                payload = json.dumps(
                {
                        "MerchantOrderNo": 'SO-'+str(sale_order.id),
                        "OrderId": sale_order.channelengine_orderId
                }
                )
                headers = {
                    'Content-Type': 'application/json'
                }

                response = requests.request("POST", url, headers=headers, data=payload)
                if response.status_code == 201:
                    sale_order.channelengine_orderStatus = 'IN_PROGRESS'
                    #fetch merchant order no for shipment
                    # https://vandewaetere-trading-bv-dev.channelengine.net/api/v2/orders?apikey=b536e286af2ac6436fdc5c926315d822166cd64c&Id=10
                    innerurl=cred.channel_engine_url+"/orders?apikey="+cred.api_key
                    innerresponse = requests.request("GET", innerurl, headers={}, data={})
                    innerdictt=innerresponse.json()
                    innerContentData = innerdictt['Content']
                    for innerData in innerContentData:
                        if innerData['Id'] == sale_order.channelengine_orderId:
                            sale_order.channelengine_merchantOrderNo = innerData['MerchantOrderNo']
                            break
                else:
                    raise UserError('An Error occurred while processing the order on channel engine')
                    # raise UserError(response.text)
                    
            elif data['Status']=='IN_PROGRESS':
                sale_order.channelengine_orderStatus = 'IN_PROGRESS'
            
   
class inheritedCompany(models.Model):
    _inherit="res.partner"

    def sync_order_customer(self):
        # customer=self.env['res.partner'].search([])
        self.create_contact_order()
    
    #Asir
    def create_contact_order(self):
        api_info=self.env['channelengine.credential'].search([("isActive",'=',True)])
        cred=api_info[0]
        url=cred.channel_engine_url+"/orders/new?apikey="+cred.api_key
        response = requests.request("GET", url, headers={}, data={})
        dictt=response.json()
        ContentData = dictt['Content']
    
        for data in ContentData:
            #check existing sale order
            existing_order = self.env['sale.order'].search([('channelengine_orderId', '=', data['Id'])])
            if not existing_order:
                order_lines = []
                #check existing billing customer
                existing_billing_customer = self.env['res.partner'].search([('email','=',data['Email'])])
                if not existing_billing_customer:
                    bfname=data['BillingAddress']['FirstName']
                    blname=data['BillingAddress']['LastName']
                    billingfullname=bfname+' '+blname
                    billing_country_code=data['ShippingAddress']['CountryIso']
                    billing_odoo_country=self.env["res.country"].search([('code', '=',billing_country_code)])
                    billing_customer=self.env['res.partner'].create({
                        'name':billingfullname,
                        'company_type': 'person',
                        'email': data['Email'],
                        'type':'invoice',
                        'street': data['BillingAddress']['HouseNr'] if data['BillingAddress']['HouseNr'] else False,
                        'street2': data['BillingAddress']['StreetName'] if data['BillingAddress']['StreetName'] else False,
                        'zip': data['BillingAddress']['ZipCode'] if data['BillingAddress']['ZipCode'] else False,
                        'city':data['BillingAddress']['City'] if data['BillingAddress']['City'] else False,
                        'country_id':billing_odoo_country.id,

                    })
                #check existing shipping customer
                existing_shipping_customer = self.env['res.partner'].search([('street','=',data['ShippingAddress']['HouseNr']),('street2','=',data['ShippingAddress']['StreetName']),('city','=',data['ShippingAddress']['City'])])
                if not existing_shipping_customer:
                    sfname=data['ShippingAddress']['FirstName']
                    slname=data['ShippingAddress']['LastName']
                    shippingfullname=sfname+' '+slname
                    shipping_country_code=data['ShippingAddress']['CountryIso']
                    shipping_odoo_country=self.env["res.country"].search([('code', '=',shipping_country_code)])
                    shipping_customer=self.env['res.partner'].create({
                        'company_type': 'person',
                        "parent_id": existing_billing_customer.id if existing_billing_customer else billing_customer.id,
                        'type':'delivery',
                        'name': shippingfullname,
                        'street': data['ShippingAddress']['HouseNr'] if data['ShippingAddress']['HouseNr'] else False,
                        'street2': data['ShippingAddress']['StreetName'] if data['ShippingAddress']['StreetName'] else False,
                        'zip': data['ShippingAddress']['ZipCode'] if data['ShippingAddress']['ZipCode'] else False,
                        'city':data['ShippingAddress']['City'] if data['ShippingAddress']['City'] else False,
                        'country_id':shipping_odoo_country.id,
                    })
                else:
                    for customer in existing_shipping_customer:
                        shippingCustomerId = customer.id
                        break

                #creating sale order lines
                for line in data['Lines']:
                    product = self.env['product.product'].search([('default_code','=',line['MerchantProductNo'])])
                    if product:
                        order_lines.append((0,0,{
                            'name':product.name,
                            'product_id':product.id,
                            'product_uom_qty': line['Quantity'],
                            'product_uom': product.uom_id.id,
                            'price_unit': line['UnitPriceInclVat'],
                            'tax_id': False,
                        }))
                
                #add shipping
                if product:
                    order_lines.append((0,0,{
                        'name':cred.shipping_product.name,
                        'product_id':cred.shipping_product.id,
                        'product_uom_qty': 1,
                        'product_uom': cred.shipping_product.uom_id.id,
                        'price_unit': data['ShippingCostsInclVat'],
                        'tax_id': False,
                    }))

                sale_order = self.env['sale.order'].create({
                    'state': 'draft',
                    'partner_id':existing_billing_customer.id if existing_billing_customer else billing_customer.id,
                    'partner_invoice_id':existing_billing_customer.id if existing_billing_customer else billing_customer.id,
                    'partner_shipping_id':shippingCustomerId if existing_shipping_customer else shipping_customer.id,
                    'channelengine_orderId':data['Id'],
                    'channelengine_orderStatus': data['Status'],
                    'channelengine_merchantOrderNo': data['MerchantOrderNo'],
                    'order_line': order_lines,
                })
# class inheritedCategory(models.Model):
#     _inherit="product.category"
#     def all_true(self):
#         for records in self:
#             records.category_sync=True

# class inheritedParent(models.Model):
#     _inherit="product.template"
#     def parent_true(self):
#         for records in self:
#             records.product_template_sync=True

# class inheritedChild(models.Model):
#     _inherit="product.product"
#     def child_true(self):
#         for records in self:
#             records.product_sync=True

    

    



                

                            































































                        

                   
                        
    #  main_comp=self.env['res.partner'].search([('company_type','=','company'),('phone','=','company')])
        #         for address in main_comp.child_ids:
        #              if (address.type=='invoice' in customer.child_ids) and (address.type=='delivery' in customer.child_ids):
        #                 raise UserError("has bith childs")
        #              else:
        #                 raise UserError("has no childs")

        #                 billing=self.env['res.partner'].create({
        #                 'name':billingfullname,
        #                 'company_type': 'person',
        #                 'type':"invoice",
        #                 "parent_id":main.id,
        #                 'street': x['BillingAddress']['HouseNr'],
        #                 'street2': x['BillingAddress']['StreetName'],
        #                 'zip': x['BillingAddress']['ZipCode'],
        #                 'city':x['BillingAddress']['City'],
        #                 'country_id':billing_oddo_Country.id,
        # })
        #                 shipping=self.env['res.partner'].create({
        #                 'company_type': 'person',
        #                 "parent_id":main.id,
        #                 'type':'delivery',
        #                 'name': shippingfullname,
        #                 'street': x['ShippingAddress']['HouseNr'],
        #                 'street2': x['ShippingAddress']['StreetName'],
        #                 'zip': x['ShippingAddress']['ZipCode'],
        #                 'city':x['ShippingAddress']['City'],
        #                 'country_id':shipping_oddo_Country.id,


        #         })
                    
                            

    


              