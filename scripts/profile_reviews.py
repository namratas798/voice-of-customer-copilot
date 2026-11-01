import json, re, collections, statistics
import sys
d = json.load(open(sys.argv[1]))
n=len(d)
dates=sorted(r["at"] for r in d)
print("n",n,"range",dates[0][:10],"->",dates[-1][:10])
days=collections.Counter(r["at"][:10] for r in d)
print("avg reviews/day",round(n/len(days),1),"days covered",len(days))
print("rating dist",sorted(collections.Counter(r["score"] for r in d).items()))
ver=collections.Counter(r["appVersion"] for r in d)
print("missing version",ver.get(None,0),"| top versions",ver.most_common(6))
lens=[len(r["content"].split()) for r in d]
print("words median",statistics.median(lens),"| <=3 words",round(100*sum(l<=3 for l in lens)/n),"% | >=20 words",round(100*sum(l>=20 for l in lens)/n),"%")
nonascii=sum(bool(re.search(r"[^\x00-\x7F]",r["content"])) for r in d)
hin=set("hai nahi nhi bahut bhi kya mera mere ho hota karo kar raha rha hain h ka ki ke se mein me aur ye toh to paisa nahin accha acha bekar bakwas".split())
def hing(t):
    w=re.findall(r"[a-z]+",t.lower()); return len(w)>0 and sum(x in hin for x in w)/len(w)>=0.15
dev=sum(bool(re.search(r"[ऀ-ॿ]",r["content"])) for r in d)
hl=sum(hing(r["content"]) for r in d if not re.search(r"[ऀ-ॿ]",r["content"]))
print("Devanagari",round(100*dev/n,1),"% | Romanized-Hinglish (heuristic)",round(100*hl/n,1),"% | other non-ASCII (emoji etc)",round(100*nonascii/n,1),"%")
lowsub=[r for r in d if r["score"]<=2 and len(r["content"].split())>=8]
print("1-2 star with >=8 words:",len(lowsub))
print("replied by dev:",sum(bool(r["replyContent"]) for r in d))
print("thumbsUp>0:",sum(r["thumbsUpCount"]>0 for r in d))
import random; random.seed(1)
for r in random.sample(lowsub,6): print(r["score"],r["appVersion"],"|",r["content"][:160].replace("\n"," "))
