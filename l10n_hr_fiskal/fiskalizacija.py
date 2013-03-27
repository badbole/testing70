# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Module: l10n_hr_fiskal
#    Author: Davor Bojkić
#    mail:   bole@dajmi5.com
#    Copyright (C) 2012- Daj Mi 5, 
#                  http://www.dajmi5.com
#    Contributions: Hrvoje ThePython - Free Code!
#                   Goran Kliska (AT) Slobodni Programi
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
import logging
from openerp.osv import fields, osv, orm
import datetime , tools
import uuid
from fiskal import *
from openerp.tools.translate import _


class res_users(osv.osv):
    _inherit = "res.users"
    _columns = {
        'oib': fields.related('partner_id','vat', string='OIB osobe' ), # relation='res.partner'
        }
res_users()

class res_company(osv.osv):
    _inherit = "res.company"
    _columns = {
        'fina_certifikat_id': fields.many2one('crypto.certificate', string="Fiskal certifikat",
            domain="[('cert_type', 'in', ('fina_demo','fina_prod') )]", #todo company_id
            help="Aktivni FINA certifikat za fiskalizaciju.",
            ),    
        'fiskal_prostor_ids': fields.one2many('fiskal.prostor','company_id', string="Poslovni prostori",
            help="Poslovni prostori (fiskalizacija).",
            ),    
    }


class fiskal_prostor(osv.Model):
    _name = 'fiskal.prostor'
    _description = 'Podaci o poslovnim prostorima za potrebe fiskalizacije'
    
    _columns = {
        'name': fields.char('Naziv poslovnog prostora', size=128 , select=1),
        'company_id':fields.many2one('res.company','Tvrtka', required="True", help='Cerificate is used for this company only.'),
        'oznaka_prostor': fields.char('Oznaka poslovnog prostora', required="True", size=20),
        'datum_primjene': fields.datetime('Datum', help ="Datum od kojeg vrijede navedeni podaci"),
        'ulica': fields.char('Ulica', size=100),
        'kbr': fields.char('Kucni broj', size=4),
        'kbr_dodatak': fields.char('Dodatak kucnom broju', size=4),
        'posta': fields.char('Posta', size=12),
        'naselje': fields.char('Naselje', size=35),
        'opcina'   :fields.char('Naziv opcine ili grada', size=35, required="True"),
        'sustav_pdv':fields.boolean('U sustavu PDV-a'),
        'radno_vrijeme' : fields.char('Radno Vrijeme', required="True", size=1000),
        'sljed_racuna':fields.selection ((('N','Na nivou naplatnog uredjaja'),('P','Na nivou poslovnog prostora')),'Sljed racuna'),
        'spec':fields.char('OIB Informaticke tvrtke', required="True", size=1000),
        'uredjaj_ids': fields.one2many('fiskal.uredjaj','prostor_id','Uredjaji'),
        'state':fields.selection ((  ('draft','Upis')
                                    ,('active','Aktivan')
                                    ,('closed','Zatvoren')
                                   )
                                  ,'Status zatvaranja'),
        
                }

    _defaults = {
                 'sustav_pdv':"True",
                 'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'fiskal.prostor', context=c),
                 'sljed_racuna':"P",
                 }

    _constraints={
                  
                  }
    
    def validate(self,cr,uid,ids):
        #kbr must be numeric 
        #posta = zip (numeric)
        return True
      
    def get_fiskal_data(self, cr, uid, company_id=False, context=None):
        fina_cert = False
        if not company_id:
            user_obj = self.pool.get('res.users')
            company_id = user_obj.browse(cr, uid, [uid])[0].company_id.id
        company_obj = self.pool.get('res.company')    
        company = company_obj.browse(cr, uid, [company_id])[0]

        fina_cert = company.fina_certifikat_id

        if not fina_cert:
            raise osv.except_osv(_('Error'), _('No valid certificates found!'))
            return False
        cert_type = fina_cert.cert_type
        if not cert_type in ('fina_demo','fina_prod'):
            return False
        if cert_type == 'fina_demo':
            file_name = "FiskalizacijaServiceTest.wsdl"
        elif cert_type == 'fina_prod':
            file_name = "FiskalizacijaService.wsdl"
        wsdl_file = 'file://' + os.path.join(os.path.dirname(os.path.abspath(__file__)),'wsdl',file_name)
        
        if not ( fina_cert.state=='confirmed' and fina_cert.csr and fina_cert.crt):
            return False, False, False

        #radi ako je server pokrenut sa -c: path 
        path = os.path.join(os.path.dirname(os.path.abspath(config.rcfile)),'oe_fiskal')
        if not os.path.exists(path):
            os.mkdir(path,0777) #TODO 0660 or less

        key_file = os.path.join(path, "{0}_{1}_{2}_key.pem".format(cr.dbname, company_id, fina_cert.id) )         
        cert_file= os.path.join(path, "{0}_{1}_{2}_crt.pem".format(cr.dbname, company_id, fina_cert.id) )

        for file in (key_file, cert_file):
            if not os.path.exists(file):
                with open(file, mode='w') as f:
                    content = file.endswith('_key.pem') and fina_cert.csr or fina_cert.crt
                    f.write(content)
                    f.flush()

        return wsdl_file, key_file, cert_file
        

    def button_test_echo(self, cr, uid, ids, fields, context=None):
        
        if context is None:
            context ={}
        
        for prostor in self.browse(cr, uid, ids):
            wsdl, key, cert = self.get_fiskal_data(cr, uid, company_id=prostor.company_id.id)
            a = Fiskalizacija()
            start_time=a.time_formated() #vrijeme pocetka obrade
            a.init('Echo', wsdl, key, cert)
            odgovor = a.echo()
            #TODO: BB : kaj ak nema odgovora?
            
        stop_time=a.time_formated()

        t_obrada=stop_time['time_stamp']-start_time['time_stamp']
        time_ob='%s.%s s'%(t_obrada.seconds, t_obrada.microseconds)
               
        values={
                'name':str(uuid.uuid1()),
                'type':'echo',
                'sadrzaj':odgovor[1],
                'timestamp':start_time['time_stamp'], 
                'time_obr':time_ob,
                'odgovor':odgovor[0]
                
                }
        return self.pool.get('fiskal.log').create(cr,uid,values,context=context)
        
    def button_prostor_prijava(self, cr, uid, ids, fields, context=None):

        prostor=self.browse(cr, uid, ids)[0]
        wsdl, cert, key = self.get_fiskal_data(cr, uid, company_id=prostor.company_id.id)
        if not wsdl:
            return False
        a = Fiskalizacija()
        a.set_start_time()
        a.init('PoslovniProstor', wsdl, cert, key)
                
        if not prostor.datum_primjene:
            datum_danas=a.start_time['datum']
        else: 
            datum_danas = prostor.datum_primjene 
            #BB: hmm, dali bas ovo ovdje? 
            """ako ponavljam slanje, opet uzimam trenutni datum slanja!
            		ovo double check!!
        			"""
        ##prvo punim zaglavlje
        a.zaglavlje.DatumVrijeme = a.start_time['datum_vrijeme']
        a.zaglavlje.IdPoruke = str(uuid.uuid1()) #moze i 4 
        ## podaci o pos prostoru
        a.pp = a.client2.factory.create('tns:PoslovniProstor') 
        a.pp.Oib= prostor.company_id.partner_id.vat[2:] #'57699704120' Mora odgovarati OIB-u sa Cert-a
        a.pp.OznPoslProstora=prostor.oznaka_prostor
        a.pp.RadnoVrijeme=prostor.radno_vrijeme
        a.pp.DatumPocetkaPrimjene=datum_danas 
        a.pp.SpecNamj =prostor.spec  #57699704120'
        
        #Mogući su i "ostali" tipovi  
        adresni_podatak = a.client2.factory.create('tns:AdresniPodatakType')
        adresa = a.client2.factory.create('tns:Adresa')
        
        adresa.Ulica= prostor.ulica
        if prostor.kbr:
            adresa.KucniBroj=prostor.kbr  
        if prostor.kbr_dodatak:
            adresa.KucniBrojDodatak=prostor.kbr_dodatak
        
        adresa.BrojPoste=prostor.posta  #'10020'
        adresa.Naselje=prostor.naselje  #'Botinec'
        adresa.Opcina= prostor.opcina  #'Novi Zagreb'
        
        adresni_podatak.Adresa = adresa
        a.pp.AdresniPodatak = adresni_podatak
        
        a.pp.__delattr__('OznakaZatvaranja') ##hmhmmm i ovo treba paziti kak sa time! jer mora jednom imati i opciju zatvaranja!
        
        odgovor = a.posalji_prostor()

        a.set_stop_time()
        t_obrada=a.stop_time['time_stamp']-a.start_time['time_stamp']
        time_ob='%s.%s s'%(t_obrada.seconds, t_obrada.microseconds)
        ##jos da si i zapisem datum primjene u bazu... 
        datum_prim=datetime.now()
        #if odgovor[0]==200: zapšisati samo ako je poruka prošla i vratila s ebez greske!
        #self.write(cr,uid,[id],{'datum_primjene': datum_prim}) #BB: ovo ne zapise nis???
            
        values={
                'name': a.zaglavlje.IdPoruke,
                'type':'prostor_prijava',
                'sadrzaj':odgovor[1],
                'timestamp':a.stop_time['time_stamp'], 
                'time_obr':time_ob,
                #'res_user_id':uid,
                'odgovor': odgovor[0],
                'fiskal_prostor_id':prostor.id
                }
        
        return self.pool.get('fiskal.log').create(cr,uid,values,context=context)
        #return True
    
    

class fiskal_uredjaj(osv.Model):
    _name = 'fiskal.uredjaj'
    _description = 'Podaci o poslovnim prostorima za potrebe fiskalizacije'

    def name_get(self, cr, uid, ids, context=None):
        res = {}
        for u in self.browse(cr, uid, ids, context=context):
            res[u.id] = ' / '.join( (u.prostor_id.name, u.name) )
        return res.items()
    _columns = {
        'name': fields.char('Naziv naplatnog uredjaja', size=128 , select=1),
        'prostor_id':fields.many2one('fiskal.prostor','Prostor',help='Prostor naplatnog uredjaja.'),
        'oznaka_uredjaj': fields.integer('Oznaka naplatnog uredjaja', required="True" ),
                }

class fiskal_log(osv.Model):
    _name='fiskal.log'
    _description='Fiskal log'    
    
    def _get_log_type(self,cursor,user_id, context=None):
        return (('prostor_prijava','Prijava Prostora'),
                ('prostor_odjava','Prijava Prostora'),
                ('racun','Fiskalizacija racuna'),
                ('racun_ponovo','Ponovljeno slanje racuna'),
                ('echo','Echo test poruka '),
                ('other','Other types')
               )
    _columns ={
        'name': fields.char('Oznaka', size=40, help="Jedinstvena oznaka komunikacije "),
        'type': fields.selection (_get_log_type,'Vrsta poruke'),
        'invoice_id': fields.many2one('account.invoice', "Racun"),
        'fiskal_prostor_id': fields.many2one('fiskal.prostor', "P.prostor"),
        'sadrzaj':fields.text('Poslana poruka'),
        'odgovor':fields.text('Odgovor'),
        'greska':fields.text('Greska'),
        'timestamp':fields.datetime('TimeStamp'),
        'time_obr':fields.char('Time for response',size=16,help='Vrijeme obrade podataka'), #vrijeme obrade prmljeno_vrijeme-poslano_vrijem
        #'origin_id':fields.integer('Origin'), # id dokumenta sa kojeg dolazi.. za prostor i za racun, echo ne koristi.
        'user_id': fields.many2one('res.users', 'User',readonly=False),
    }


""" TODO
class l10n_hr_log(osv.Model):
    _name='l10n.hr.log'
    _description='Official communicatins log'    
    
    def _get_log_type(self,cursor,user_id, context=None):
        return (('prostor','Prijava Prostora'),
                ('racun','Fiskalizacija racuna'),
                ('echo','Echo test message '),
                ('other','Other types ->TODO')
               )
    _columns ={
        'name': fields.char('Oznaka', size=128, help="Jedinstvena oznaka komunikacije "),
        'type': fields.selection (_get_log_type,'Log message Type'),
        'sadrzaj':fields.text('Message context'),
        'odgovor':fields.text('Message reply'),
        'timestamp':fields.datetime('TimeStamp'),
        'time_obr':fields.char('Time for response',size=16,help='Vrijeme obrade podataka'), #vrijeme obrade prmljeno_vrijeme-poslano_vrijem
        #'l10n_hr_fis_pprostor_id':fields.many2one('l10n_hr_fis_pprostor','l10n_hr_fis_pprostor_log_id','Prostor'),
        'origin_id':fields.integer('Origin'), # id dokumenta sa kojeg dolazi.. za prostor i za racun, echo ne koristi.
        #'users_id':fields.many2one('res.users', 'User') ## ovo cak i netreba obzirom na create i write uide !!
        'user_id': fields.many2one('res.users', 'User',readonly=False),
 
        }
l10n_hr_log()

"""


"""
BOLE: 
leftovers from beginning, to be removed!

def button_test_racun(self,cr,uid,ids,fields,context=None):
        logs_obj=self.pool.get('l10n.hr.log')
        
        a = Fiskalizacija()
        tstamp = datetime.datetime.now()
        tmptime  = '%s.%s.%s %s:%s:%s' % (tstamp.day, tstamp.month, tstamp.year, tstamp.hour, tstamp.minute, tstamp.second)
        a.t = tstamp
        # podrazumijevam da su podaci obavezni i ne provjeravam jel postoje...
        a.zaglavlje.DatumVrijeme = '%02d.%02d.%02dT%02d:%02d:%02d' % (tstamp.day, tstamp.month, tstamp.year, tstamp.hour, tstamp.minute, tstamp.second)
        a.zaglavlje.IdPoruke = str(uuid.uuid4())
        
        #main_comp=self.pool.get('res.company').browse()
        a.racun.Oib = "57699704120" #ucitaj ! OIB korisnika
        a.racun.USustPdv = 'true'  ## sustav_pdv
        a.racun.DatVrijeme = a.zaglavlje.DatumVrijeme 
        a.racun.OznSlijed = 'P' ## sljed_racuna
        a.racun.BrRac.BrOznRac = '1'
        a.racun.BrRac.OznPosPr = 'TESTIRAMO' ## name !! pazi !! nesmije imati razmake u nazivu.. prije sljanaj replace ' '->'' !!!
        a.racun.BrRac.OznNapUr = '12'  ## oznaka_pp
        a.porez = a.client2.factory.create('tns:Porez')
        a.porez.Stopa = "25.00"
        a.porez.Osnovica = "100.00"
        a.porez.Iznos = "25.00"
        a.racun.Pdv.Porez.append(a.porez)

        a.racun.IznosUkupno = "125.00" # 
        a.racun.NacinPlac = "G" # Nacin placanja
        a.racun.OibOper = "57699704120"
        a.racun.NakDost = "false"  ##TODO rutina koja provjerava jel prvi puta ili ponovljeno sranje!

        a.izracunaj_zastitni_kod(tmptime)
        #odgovor_string = a.echo()  moze i ovo radi!
        odgovor_string=a.posalji_racun()
        odgovor_array = odgovor_string[1]
        # ... sad tu ima odgovor.Jir
        
        if odgovor_array.Jir:
            jir ='JIR - '+ odgovor_array.Jir
        else :
            jir='greska u komunikaciji'
        ##ovo sam dodao samo da vidim vrijeme odaziva...
        tstamp2=datetime.datetime.now()
        vrijeme_obrade=tstamp2-tstamp
        time_obr='%s.%s s'%(vrijeme_obrade.seconds, vrijeme_obrade.microseconds)
        ################################################
        
        odgovor= odgovor_string  
        values={
                'name':jir,
                'type':'racun',
                'sadrzaj':odgovor,
                'timestamp':tstamp, 
                'time_obr':time_obr,
                
                }
        log_id=logs_obj.create(cr,uid,values,context=context)
        return log_id
#fiskal_pprostor()


"""