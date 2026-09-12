from dataclasses import dataclass
@dataclass(frozen=True)
class CarSpec:
 key:str; name:str; price:int; available:bool=True; shoti_eligible:bool=False
_DATA=[('pride_131','پراید ۱۳۱',780000000),('pride_111','پراید ۱۱۱',700000000),('tiba','تیبا',1059000000),('tiba2','تیبا ۲',1060000000),('saina','ساینا',1420000000),('quick','کوییک',1430000000),('peugeot405','پژو ۴۰۵',1220000000),('peugeot_pars','پژو پارس',1693000000),('peugeot206','پژو ۲۰۶',1200000000),('peugeot207','پژو ۲۰۷',2050000000),('samand','سمند',1650000000),('samand_soren','سمند سورن',1860000000),('dena','دنا',2460000000),('dena_plus','دنا پلاس',3375000000),('rana','رانا',1900000000),('zantia','زانتیا',1200000000),('l90','ال۹۰',1500000000),('shahin','شاهین',2200000000)]
CAR_CATALOG=tuple(CarSpec(k,n,p,True,n in {'پژو ۴۰۵','پژو پارس','زانتیا','سمند'}) for k,n,p in _DATA)
def car(key): return next((x for x in CAR_CATALOG if x.key==key),None)
