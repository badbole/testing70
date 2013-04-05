# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Module: account_storno
#    Author: Goran Kliska
#    mail:   gkliskaATgmail.com
#    Copyright (C) 2011- Slobodni programi d.o.o., Zagreb
#    Contributions: 
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
import time
from osv import fields, osv
from tools.translate import _
import netsvc

class account_invoice(osv.osv):
    _inherit = "account.invoice"

    def refund(self, cr, uid, ids, date=None, period_id=None, description=None, journal_id=None):
        #Where is the context, per invoice method?
        #This approach is slow, updating after creating, but maybe better than copy-paste whole method
        res = super(account_invoice, self).refund(cr, uid, ids, date=date, period_id=period_id, description=description, journal_id=journal_id)
        for invoice in self.pool.get('account.invoice').browse(cr, uid, res):
            if invoice.journal_id.posting_policy == 'storno':
                for inv_line in invoice.invoice_line:
                    self.pool.get('account.invoice.line').write(cr, uid, 
                                [inv_line.id],
                                {'quantity': inv_line.quantity * (-1) })
                for tax_line in invoice.tax_line:
                    if tax_line.manual or True:
                        self.pool.get('account.invoice.tax').write(cr, uid, 
                                    [tax_line.id],
                                    {'base': tax_line.base * (-1),
                                     'amount': tax_line.amount * (-1),
                                     'base_amount': tax_line.base_amount * (-1),
                                     'tax_amount': tax_line.tax_amount * (-1), 
                                     })
        return res

    
class account_invoice_refund(osv.osv_memory):
    _inherit = "account.invoice.refund"

    def _get_journal(self, cr, uid, context=None):
            """"in Croatia, for out invoice refunds must go to same journal  #TODO for localization
            """
            #borrowed from Akretion account_journal_sale_refund_link
            #compatibility with crm_claim_rma module
            invoice_id = context.get('invoice_ids', [context['active_id']])[0]
            invoice = self.pool.get('account.invoice').browse(cr, uid, invoice_id, context=context)
            refund_journal_id = invoice.journal_id.refund_journal_id
            if refund_journal_id:
                return refund_journal_id.id
            elif invoice.journal_id.posting_policy == 'storno':
                return False  #meaning: same journal as original 
            else:
                return super(account_invoice_refund, self)._get_journal(cr, uid, context)

    _defaults = {
        'journal_id': _get_journal,
        'filter_refund': 'modify',
        }

    def fields_view_get(self, cr, uid, view_id=None, view_type=False, context=None, toolbar=False, submenu=False):
        journal_obj = self.pool.get('account.journal')
        user_obj = self.pool.get('res.users')
        res = super(account_invoice_refund,self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)
        company_id = user_obj.browse(cr, uid, uid, context=context).company_id.id
        #I would love to have invoice.journal_id.posting_policy here
        invoice_type = context.get('type', 'all')
        if invoice_type in ('out_invoice', 'out_refund'):
            journal_types = ('sale','sale_refund')
        elif invoice_type in ('in_invoice', 'in_refund'):
            journal_types = ()
        else:
            journal_types = ('sale','sale_refund','purchase','purchase_refund') 
        journal_select = journal_obj._name_search(cr, uid, '', [('type', 'in', journal_types), ('company_id','child_of',[company_id])], context=context)
        #original for loop needed??? 
        res['fields']['journal_id']['selection'] = journal_select
        return res

account_invoice_refund()
