import {afterEach,describe,expect,it,vi} from 'vitest';
import {makeFormatters} from './i18n';
import {listModelVersions,probeGateway,requestDownload,streamAgentChat} from './api';

afterEach(()=>{vi.unstubAllGlobals();vi.useRealTimers()});
async function connect(response:Response){
 const mock=vi.fn().mockResolvedValueOnce(Response.json({})).mockResolvedValueOnce(response);
 vi.stubGlobal('fetch',mock);await probeGateway();return mock;
}
describe('third audit counterexamples',()=>{
 it('cleans up a rejected probe timer',async()=>{
   vi.useFakeTimers();vi.stubGlobal('fetch',vi.fn().mockRejectedValue(Error('offline')));
   expect(await probeGateway()).toBe(false);expect(vi.getTimerCount()).toBe(0);
 });
 it('recognizes SSE delimiters split between network chunks',async()=>{
   const chunks=['event: message\r','\ndata: {"text":"ok"}\r\n\r','\n'];
   await connect(new Response(new ReadableStream({start(c){chunks.forEach(v=>c.enqueue(new TextEncoder().encode(v)));c.close()}})));
   const listener=vi.fn();await streamAgentChat('test',listener);expect(listener).toHaveBeenCalledWith(expect.objectContaining({text:'ok'}));
 });
 it('preserves the final snapshot flag',async()=>{
   await connect(new Response('event: message\ndata: {"text":"full answer","final":true}\n\n'));
   const listener=vi.fn();await streamAgentChat('test',listener);expect(listener).toHaveBeenCalledWith(expect.objectContaining({final:true}));
 });
 it('does not discard listener errors as malformed JSON',async()=>{
   await connect(new Response('event: message\ndata: {"text":"ok"}\n\n'));
   await expect(streamAgentChat('test',()=>{throw Error('consumer failed')})).rejects.toThrow('consumer failed');
 });
 it('keeps a real epoch timestamp instead of replacing it with today',async()=>{
   await connect(Response.json({versions:[{key:['crop','region'],timestamp:'1970-01-01T00:00:00Z',version:1}]}));
   expect((await listModelVersions())[0].createdAt).toBe(0);
 });
 it('never expands a broken download geometry to a global polygon',async()=>{
   const mock=await connect(Response.json({job_id:'should-not-exist'}));
   await expect(requestDownload('scene',[[0,0]],{from:'2024-01-01',to:'2024-01-02',sensor:'landsat'})).rejects.toThrow('Invalid ROI');
   expect(mock).toHaveBeenCalledTimes(1);
 });
 it('formats an unknown date without unmounting the view',()=>expect(makeFormatters('fa').date('not-a-date')).toBe('—'));
 it('short times keep the day period and omit seconds',()=>{
   const d=new Date(2024,0,1,13,24,35);expect(makeFormatters('en').time(d,true)).toMatch(/01:24\s*PM/);
 });
});
