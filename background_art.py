"""Specific 2D sets for rural river stories and motorbike workshops."""
from PIL import Image, ImageDraw
from scene_backgrounds import normalize


def draw_story_set(bid, description, path, size=(1280, 720)):
    key = normalize(str(bid) + ' ' + description)
    workshop = any(word in key for word in ('tiem_sua_xe', 'tiem sua xe', 'sua xe may'))
    river = any(word in key for word in ('ven_rach', 'con rach', 'nha la', 'cot tram'))
    if not workshop and not river:
        return False
    im = Image.new('RGB', (1280, 720))
    d = ImageDraw.Draw(im)
    def house(x, y, scale=1, near=False):
        def box(a,b,c,e): return tuple(int(v) for v in (x+a*scale,y+b*scale,x+c*scale,y+e*scale))
        outline = '#453c2e'
        for xx in (18, 108, 190):
            d.polygon([(x+xx*scale,y+130*scale),(x+(xx+12)*scale,y+130*scale),(x+(xx+7)*scale,y+242*scale),(x+(xx-2)*scale,y+242*scale)],fill='#554b35')
        d.rectangle(box(0,25,220,165),fill='#968469',outline=outline,width=max(2,int(3*scale)))
        for xx in range(5,220,14): d.line([(x+xx*scale,y+35*scale),(x+(xx-4)*scale,y+164*scale)],fill='#73674e',width=max(1,int(2*scale)))
        d.polygon([(x-28*scale,y+38*scale),(x+100*scale,y-40*scale),(x+250*scale,y+38*scale)],fill='#655b3f',outline=outline,width=max(2,int(3*scale)))
        for xx in range(-15,240,12):d.line([(x+100*scale,y-35*scale),(x+xx*scale,y+38*scale)],fill='#887851',width=max(1,int(2*scale)))
        d.rectangle(box(75,65,140,165),fill='#302c29')
        d.rectangle(box(20,65,55,105),fill='#3c4239',outline=outline,width=2)
        d.line([(x-5*scale,y+165*scale),(x+238*scale,y+165*scale)],fill='#473f31',width=max(3,int(6*scale)))
        if near:
            d.line([(x+160*scale,y+55*scale),(x+275*scale,y+65*scale)],fill='#493c31',width=3)
            for xx,col in ((180,'#8b6260'),(210,'#557b7a'),(240,'#c4ab7b')):
                d.polygon([(x+xx*scale,y+60*scale),(x+(xx+22)*scale,y+61*scale),(x+(xx+20)*scale,y+105*scale),(x+(xx-3)*scale,y+102*scale)],fill=col)
    if river:
        for y in range(720):
            if y<330:
                t=y/330;col=tuple(int(a+(b-a)*t) for a,b in zip((132,164,169),(207,200,170)))
            else:
                t=(y-330)/390;col=tuple(int(a+(b-a)*t) for a,b in zip((132,122,83),(91,91,69)))
            d.line((0,y,1280,y),fill=col)
        d.polygon([(0,303),(120,278),(260,294),(450,266),(620,301),(800,270),(1010,287),(1280,269),(1280,390),(0,380)],fill='#657f62')
        house(110,255,.58);house(900,250,.62)
        for x,y in ((30,350),(330,340),(810,336),(1200,330)):
            d.line([(x,y+35),(x-8,y-80)],fill='#686747',width=12)
            for dx,dy in ((-90,-20),(-60,-75),(0,-100),(60,-85),(100,-20)):
                d.polygon([(x-8,y-65),(x+dx,y+dy-65),(x+dx*.65,y+dy-35)],fill='#4a7052')
        for y in range(390,720,25):
            for x in range((y*3)%180-100,1280,210):d.line((x,y,x+100,y-3),fill='#a49b72',width=2)
        home = 'nha_la' in key or 'vach la' in key
        if home:
            house(30,255,1.75,True)
            d.polygon([(0,620),(420,530),(500,570),(90,720),(0,720)],fill='#66553d')
        else:
            d.polygon([(530,720),(720,720),(700,430),(615,430)],fill='#786347')
            for y in range(440,720,24):d.line((600-(y-440)*.25,y,700+(y-440)*.07,y),fill='#4b4435',width=4)
            for x in (580,740):d.line((x,710,x+10,540),fill='#564b36',width=9)
        d.polygon([(875,490),(1100,500),(1050,541),(928,531)],fill='#594c36',outline='#393e32',width=4)
        d.line((910,505,1060,510),fill='#a18b60',width=5)
    else:
        d.rectangle((0,0,1280,720),fill='#a9a393')
        d.rectangle((0,450,1280,720),fill='#77756b')
        d.polygon([(0,0),(1280,0),(1280,80),(0,120)],fill='#535c5a')
        for x in range(0,1280,95):d.line((x,0,x+65,95),fill='#727770',width=4)
        d.rectangle((790,105,1240,490),fill='#c3c8ba',outline='#424b47',width=16)
        d.rectangle((805,330,1225,490),fill='#717772')
        for x,col in ((830,'#c4b59b'),(970,'#bda08b'),(1110,'#a9b5ac')):
            d.rectangle((x,180,x+105,330),fill=col,outline='#81877a',width=3)
            d.rectangle((x+28,240,x+72,330),fill='#566461')
        d.rectangle((80,160,665,385),fill='#7e8272',outline='#48564e',width=6)
        for x in range(125,640,65):
            d.line((x,220,x,320),fill='#c4c7b8',width=8);d.ellipse((x-10,205,x+10,225),outline='#d8d7c8',width=5)
        d.rectangle((70,410,590,442),fill='#5d4d3c')
        for x in (100,530):d.rectangle((x,440,x+22,570),fill='#4d4d41')
        for x,y in ((700,410),(700,480),(700,550)):
            d.ellipse((x-53,y-53,x+53,y+53),fill='#303734',outline='#171e1f',width=8)
            d.ellipse((x-30,y-30,x+30,y+30),fill='#777b70')
        # A recognisable motorbike on the workshop floor.
        for x in (295,585):
            d.ellipse((x-68,517,x+68,653),fill='#272e2d',outline='#181f20',width=8)
            d.ellipse((x-43,542,x+43,628),fill='#9da7a0',outline='#596962',width=5)
            for dx,dy in ((40,0),(-40,0),(0,40),(0,-40)):
                d.line((x,585,x+dx,585+dy),fill='#d2d5c6',width=3)
        d.polygon([(290,575),(390,462),(493,485),(580,575),(447,590)],fill='#705b52',outline='#293d39',width=8)
        d.polygon([(370,450),(480,451),(525,490),(401,495)],fill='#8e4c44',outline='#293d39',width=5)
        d.rounded_rectangle((333,429,468,449),radius=8,fill='#29322f')
        d.line((585,585,541,425,510,391),fill='#a4ada2',width=12)
        d.line((501,391,559,388),fill='#293a34',width=10)
        d.ellipse((534,427,565,457),fill='#e1d1a2',outline='#53635a',width=4)
        d.rectangle((125,450,185,520),fill='#965f43',outline='#454e42',width=4)
    if 'dem' in key or 'ban đêm' in description.lower():
        im = Image.blend(im, Image.new('RGB',im.size,(12,22,43)),.55)
        d=ImageDraw.Draw(im)
        d.ellipse((330,300,346,323),fill='#dfb367')
    elif 'chieu' in key:
        im = Image.blend(im, Image.new('RGB',im.size,(185,119,62)),.16)
    if size != im.size: im=im.resize(size,Image.Resampling.LANCZOS)
    im.save(path)
    return True
