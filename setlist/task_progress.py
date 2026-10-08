"""Measured task timing. Unknown work never receives an invented countdown."""
import math
import time
from statistics import median


class Update(str):
    def __new__(cls,message,phase,completed,total,final=False,song=None,activity=None,selection_plan=None,eta_known=True):
        value=super().__new__(cls,message)
        value.phase=phase;value.completed=completed;value.total=total;value.final=final
        value.song=song;value.activity=activity;value.selection_plan=selection_plan
        value.eta_known=eta_known
        return value


class Timing:
    def __init__(self,estimate=None,clock=time.monotonic):
        self.clock=clock;self.started=clock();self.ended=None;self.state='running'
        # Legacy whole-job history mixes cold/warm caches and different work stages.
        # Retain the constructor contract, but only current-stage measurements drive ETA.
        self.phase=None;self.phase_start=self.started;self.done=0;self.total=0;self.final=False;self.last_update=self.started
        self.last_elapsed=0
        self.samples=[];self.sample_at=self.started;self.warm=False;self.eta_known=False

    def update(self,message):
        now=self.clock();self.last_update=now
        if not isinstance(message,Update):
            self.phase=None;self.done=0;self.total=0;self.final=False
            self.samples=[];self.warm=False;self.eta_known=False
            return
        reset=(message.phase!=self.phase or message.total!=self.total or message.completed<self.done or message.eta_known!=self.eta_known)
        if reset:
            self.phase=message.phase;self.phase_start=now;self.done=max(0,message.completed)
            self.samples=[];self.sample_at=now;self.warm=False
        elif message.completed>self.done:
            span=max(0,now-self.sample_at);units=message.completed-self.done
            if self.warm and span>0:self.samples=(self.samples+[(span/units,span)])[-8:]
            self.warm=True;self.sample_at=now
        self.done=max(self.done,max(0,message.completed));self.total=max(0,message.total);self.final=message.final
        self.eta_known=message.eta_known

    def finish(self,state):
        self.state=state;self.ended=max(self.started,self.clock())

    def snapshot(self):
        now=self.ended if self.ended is not None else self.clock()
        elapsed=max(self.last_elapsed,now-self.started,0);self.last_elapsed=elapsed
        result={'elapsedSeconds':round(elapsed,1),'etaSeconds':None,'etaScope':None,'etaState':'calculating','progressPercent':None}
        if self.state!='running':
            result['etaState']=self.state
            return result
        if self.total>0 and self.eta_known:result['progressPercent']=min(99,int(100*self.done/self.total))
        if now-self.last_update>15:
            result['etaState']='working'
            return result
        if self.eta_known and self.total>self.done and len(self.samples)>=4 and sum(s[1] for s in self.samples)>=2:
            rates=sorted(s[0] for s in self.samples);rate=median(rates)
            # Suppress estimates while per-unit costs change substantially (e.g. cache misses).
            if rates[-1]/rates[0]<=2:
                if now-self.sample_at>max(2,3*rate):result['etaState']='overrun'
                else:result.update(etaSeconds=max(1,math.ceil((self.total-self.done)*rate)),etaScope='task' if self.final else 'step',etaState='estimated')
        return result
