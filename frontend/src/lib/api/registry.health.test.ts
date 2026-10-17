import { describe, expect, it } from 'vitest'
import { summarizeClusterHealth } from './registry'
import type { ComputeNode } from '../schemas/registry'
const node = (backend: string, status: string, enabled=true, queue: string|null='q'): ComputeNode => ({id:'n',name:'target',backend,enabled,queue,health_status:status,labels:{},server_id:null,health_error:null,health_checked_at:null,version:1,created_at:'',updated_at:''})
describe('cluster connection summary',()=>{
 it('does not equate registration or Docker health with an LSF connection',()=>{
  expect(summarizeClusterHealth([node('docker','healthy'),node('lsf','unknown')]).connected).toBe(false)
 })
 it('counts verified LSF queues and excludes disabled targets',()=>{
  expect(summarizeClusterHealth([node('lsf','healthy'),node('lsf','healthy'),node('lsf','healthy',false,'disabled')])).toMatchObject({connected:true,queues:['q']})
 })
 it('retains registered queues without claiming they passed',()=>{
  expect(summarizeClusterHealth([node('lsf','unhealthy')])).toMatchObject({connected:false,queues:[],all_queues:['q']})
 })
})
