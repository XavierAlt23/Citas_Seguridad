"""Controlled local-only HTTP workload. Measures results, never asserts capacity."""
import argparse, asyncio, json, os, ssl, statistics, time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent

async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--users',type=int,default=30);parser.add_argument('--seconds',type=int,default=10);parser.add_argument('--ramp',type=float,default=0);parser.add_argument('--think',type=float,default=.2);parser.add_argument('--distinct-ips',action='store_true');args=parser.parse_args()
    if not 1<=args.users<=2000 or not 1<=args.seconds<=300: raise SystemExit('Usuarios 1–2000; segundos 1–300.')
    ctx=ssl.create_default_context(cafile=str(ROOT/'.local/tls-cert.pem'))
    timings=[]; statuses={}; errors=0; deadline=time.monotonic()+args.seconds; peak_active=0; active=0
    samples=[]
    async def sample():
        while time.monotonic()<deadline:
            sample={'time':time.time()}
            pidfile=ROOT/'.local/gunicorn.pid'
            if pidfile.exists():
                try:
                    pid=int(pidfile.read_text()); children=(Path(f'/proc/{pid}/task/{pid}/children').read_text().split()); pids=[str(pid),*children]
                    rss=0; ticks=0
                    for p in pids:
                        text=Path(f'/proc/{p}/stat').read_text().split(); ticks+=int(text[13])+int(text[14])
                        rss+=int(Path(f'/proc/{p}/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
                    sample.update(app_rss_bytes=rss,app_cpu_seconds=ticks/os.sysconf('SC_CLK_TCK'))
                except (OSError,ValueError): pass
            samples.append(sample); await asyncio.sleep(1)
    async def worker(index):
        nonlocal errors,active,peak_active
        await asyncio.sleep(args.ramp*index/args.users)
        while time.monotonic()<deadline:
            start=time.perf_counter(); writer=None
            try:
                active+=1;peak_active=max(peak_active,active)
                local_addr=(f'127.1.{index//250}.{index%250+1}',0) if args.distinct_ips else None
                reader,writer=await asyncio.wait_for(asyncio.open_connection('127.0.0.1',8443,ssl=ctx,server_hostname='localhost',local_addr=local_addr),timeout=15)
                writer.write(b'GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n');await writer.drain()
                line=await asyncio.wait_for(reader.readline(),timeout=15)
                status=int(line.split()[1]);await asyncio.wait_for(reader.read(),timeout=15)
                statuses[str(status)]=statuses.get(str(status),0)+1
            except (OSError,ValueError,IndexError,asyncio.TimeoutError): errors+=1
            finally:
                active-=1
                if writer:
                    writer.close()
                    try: await writer.wait_closed()
                    except OSError: pass
                timings.append(time.perf_counter()-start)
            await asyncio.sleep(args.think)
    started=time.perf_counter();await asyncio.gather(sample(),*(worker(i) for i in range(args.users)));elapsed=time.perf_counter()-started
    ordered=sorted(timings);failed=errors+sum(v for k,v in statuses.items() if int(k)>=400)
    report={'users_configured':args.users,'peak_active_requests':peak_active,'seconds':round(elapsed,2),'request_window_seconds':args.seconds,'ramp_seconds':args.ramp,'think_seconds':args.think,'source_ips':'distinct loopback TCP addresses' if args.distinct_ips else 'single loopback IP','requests':len(timings),'status_counts':statuses,'network_errors':errors,'error_rate':failed/max(1,len(timings)),'p95_ms':round(ordered[min(len(ordered)-1,int(len(ordered)*.95))]*1000,2) if ordered else None,'throughput_rps':round(len(timings)/elapsed,2),'process_samples':samples,'scope':'Búsqueda pública HTTPS; 429 cuenta como rechazo, no como éxito. Usuarios virtuales con pausas no equivalen a peticiones simultáneas. No prueba todos los flujos.','run_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}
    folder=ROOT/'evidence';folder.mkdir(exist_ok=True);suffix='-paced' if args.distinct_ips else '';(folder/f'load-{args.users}{suffix}.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='process_samples'},indent=2))

asyncio.run(main())
