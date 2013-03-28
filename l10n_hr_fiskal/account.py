# -*- encoding: utf-8 -*-


from openerp.osv import fields, osv

class account_journal(osv.osv):
    _inherit = "account.journal"
    _columns = {
        'fiskal_active':fields.boolean('Fiskalizacija aktivna', help="Fiskalizacija aktivna" ),
        'fiskal_uredjaj_ids': fields.many2many('fiskal.uredjaj', string='Dopusteni naplatni uredjaji'),
                }
    _defaults = {'fiskal_active': False, 
                }


class account_tax_code(osv.Model):
    _inherit = 'account.tax.code'
    def _get_fiskal_type(self,cursor,user_id, context=None):
        return [('pdv','Pdv'),
                ('pnp','Porez na potrosnju'),
                ('ostali','Ostali porezi'),
                ('oslobodenje','Oslobodjenje'),
                ('marza','Oporezivanje marze'),
                ('ne_podlijeze','Ne podlijeze oporezivanju'),
                ('naknade','Naknade (npr. ambalaza)'),
               ]
    _columns = {
        'fiskal_percent': fields.char('Porezna stopa', size=128 , help='Porezna stopa za potrebe fiskalizacije. Primjer: 25.00'),
        'fiskal_type':fields.selection(_get_fiskal_type, 'Vrsta poreza',help='Vrsta porezne grupe za potrebe fiskalizacije.'),
                }


class account_move(osv.osv):
    _inherit = 'account.move'

    def post(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        res = super(account_move,self).post(cr, uid, ids, context)
        if res:
            invoice = context.get('invoice', False)
            if not invoice:
                return res 
            if not invoice.type in ('out_invoice', 'out_refund'):  #samo izlazne racune  
                return res 
            fiskalni_sufiks = '/'.join( (invoice.uredjaj_id.prostor_id.oznaka_prostor, str(invoice.uredjaj_id.oznaka_uredjaj)))
            for move in self.browse(cr, uid, ids):
                new_name =  '/'.join( (move.name, fiskalni_sufiks) ) 
                self.write(cr, uid, [move.id], {'name':new_name})
                if invoice.journal_id.fiskal_active: #samo oznacene journale
                    self.pool.get('account.invoice').fiskaliziraj(cr, uid, invoice.id, context)
        return res
    
