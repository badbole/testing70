# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Module: account_storno - tax payment
#    Author: Goran Kliska
#    mail:   gkliskaATgmail.com
#    Copyright (C) 2011- Slobodni programi d.o.o., Zagreb
#    Contributions: 
#         
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import fields, osv, orm
import time
from tools.translate import _ 

class account_invoice(osv.osv):
    _inherit = "account.invoice"

    def line_get_convert(self, cr, uid, x, part, date, context=None):
        res=super(account_invoice,self).line_get_convert(cr, uid, x, part, date, context=context)
        if context is None:
            context = {}
        tax_code_id = res.get('tax_code_id', False)
        tax_code_obj = self.pool.get('account.tax.code')
        if tax_code_id and (res['debit'] + res['credit'] < 0.0 ) :
            tax_posting_policy = tax_code_obj.browse(cr, uid, tax_code_id).posting_policy
            invoice = context.get('invoice',False)
            if invoice and invoice.journal_id.posting_policy=='storno':
                if tax_posting_policy == 'contra':
                    res['debit'],res['credit'] = res['credit']*(-1),res['debit']*(-1)
                    res['tax_amount'] = res['tax_amount'] * (-1)
                
            if invoice and invoice.journal_id.posting_policy=='contra':
                if tax_posting_policy == 'storno':
                    res['debit'],res['credit'] = res['credit']*(-1),res['debit']*(-1)
                    res['tax_amount'] = res['tax_amount'] * (-1)
        return res
    
account_invoice()
