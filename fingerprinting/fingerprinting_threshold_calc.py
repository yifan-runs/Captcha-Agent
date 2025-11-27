import math, json

# Reuse data loaded earlier? Let's reload.
with open('/mnt/data/fingerprint_log.json') as f:
    sessions = json.load(f)

FP_MAX_DURATION = 20.0

def pathFeatures(moves, clicks):
    if len(moves) < 2:
        return dict(avg_speed=0.0, max_speed=0.0, curvature_mean=1.0, teleport_fraction=0.0, speed_std=0.0)
    TELEPORT_THRESHOLD = 3000.0
    speeds=[]
    teleports=0
    for e1,e2 in zip(moves,moves[1:]):
        dt = e2['time']-e1['time']
        if dt<=0: continue
        dx=e2['mx']-e1['mx']; dy=e2['my']-e1['my']
        dist=math.hypot(dx,dy); v=dist/dt
        speeds.append(v)
        if v>TELEPORT_THRESHOLD: teleports+=1
    if speeds:
        avg=sum(speeds)/len(speeds)
        mx=max(speeds)
        sd=(sum((v-avg)**2 for v in speeds)/len(speeds))**0.5
        tele=teleports/len(speeds)
    else:
        avg=mx=sd=tele=0.0
    curvature=1.0
    if len(clicks)>=2:
        vals=[]
        for c1,c2 in zip(clicks,clicks[1:]):
            seg=[m for m in moves if c1['time']<=m['time']<=c2['time']]
            if len(seg)<2: continue
            path=sum(math.hypot(seg[i+1]['mx']-seg[i]['mx'], seg[i+1]['my']-seg[i]['my']) for i in range(len(seg)-1))
            straight=math.hypot(seg[-1]['mx']-seg[0]['mx'], seg[-1]['my']-seg[0]['my'])
            if straight>0: vals.append(path/straight)
        if vals: curvature=sum(vals)/len(vals)
    return dict(avg_speed=avg, max_speed=mx, curvature_mean=curvature, teleport_fraction=tele, speed_std=sd)

def clickOffsets(clicks):
    offs=[]
    for e in clicks:
        if e['type']!='bubble_click': continue
        cx,cy = e['bubble_center']
        dx=e['mx']-cx; dy=e['my']-cy
        offs.append(math.hypot(dx,dy))
    if not offs: return dict(offset_mean=0.0, offset_std=0.0)
    meanOff=sum(offs)/len(offs)
    var=sum((d-meanOff)**2 for d in offs)/len(offs)
    return dict(offset_mean=meanOff, offset_std=math.sqrt(var))

def preFirstClickPath(moves, tFC):
    pre=[m for m in moves if m['time']<tFC]
    if len(pre)<2: return 0.0
    return sum(math.hypot(pre[i+1]['mx']-pre[i]['mx'],pre[i+1]['my']-pre[i]['my']) for i in range(len(pre)-1))

def computeFeatures(events):
    evs=sorted(events, key=lambda e:e['time'])
    moves=[e for e in evs if e['type']=='move']
    clicks=[e for e in evs if e['type'] in ('bubble_click','empty_click')]
    instr=[e for e in evs if e['type']=="instruction_shown"]
    start=[e for e in evs if e['type']=="session_start"]
    end=[e for e in evs if e['type']=="session_end"]
    tStart=start[0]['time'] if start else evs[0]['time']
    tEnd=end[-1]['time'] if end else evs[-1]['time']
    total=max(0,tEnd-tStart)
    feats={}
    feats['time_used_ratio']=min(1,total/FP_MAX_DURATION)
    firstClick=clicks[0]['time'] if clicks else tEnd
    instrTime=instr[0]['time'] if instr else tStart
    feats['rt_first_click']=max(0,firstClick-instrTime)
    tClicks=[e for e in clicks if e['type']=='bubble_click' and e['is_correct']]
    if tClicks:
        rts=[e['time']-instrTime for e in tClicks]
        feats['rt_mean']=sum(rts)/len(rts)
    else:
        feats['rt_mean']=total
    if len(clicks)>=2:
        times=[e['time'] for e in clicks]
        intervals=[times[i+1]-times[i] for i in range(len(times)-1)]
        meanI=sum(intervals)/len(intervals)
        varI=sum((d-meanI)**2 for d in intervals)/len(intervals)
        feats['ici_mean']=meanI
        feats['ici_cv']=math.sqrt(varI)/(meanI+1e-6)
    else:
        feats['ici_mean']=total
        feats['ici_cv']=0
    pf=pathFeatures(moves, clicks)
    feats.update(pf)
    feats['move_count']=len(moves)
    feats['click_count']=len(clicks)
    feats.update(clickOffsets(clicks))
    incorrect=sum(1 for e in clicks if e['type']=='bubble_click' and not e['is_correct'])
    empty=sum(1 for e in clicks if e['type']=='empty_click')
    feats['incorrect_bubble_clicks']=incorrect
    feats['empty_clicks']=empty
    feats['total_clicks']=len(clicks)
    feats['empty_click_ratio']= empty/len(clicks) if clicks else 0
    feats['clicks_per_second']= len(clicks)/total if total>0 else 0
    feats['visited_instruction_area']= 1.0 if any(0<=m['my']<=60 for m in moves) else 0.0
    feats['pre_first_click_path_length']= preFirstClickPath(moves, firstClick)
    feats['attempts_count']=1.0
    return feats

all_feats=[computeFeatures(s['events']) for s in sessions]

all_feats[:3]