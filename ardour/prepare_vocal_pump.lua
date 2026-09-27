-- SPDX-License-Identifier: GPL-3.0-or-later
-- Run through ardour-lua on a backed-up, closed session. Requires the supplied
-- studio-vocal-pump presets and headless sleep(). Returns a preparation function.
-- Prepared audio/MIDI returns. Inputs intentionally remain unassigned until
-- source identification; all existing processors and source outputs are kept.
return function(s, report)
assert(s and s:path(), 'No session')
for r in s:get_routes():iter() do
 for _,name in ipairs({'VOIX A','VOIX B','PUMP','VOCODEUR','VOC ACCORDS','KICK'}) do
  assert(r:name()~=name, 'Preparation already present: '..name)
 end
end
local function bus(name)
 local r=s:new_audio_route(2,2,ARDOUR.RouteGroup(),1,name,ARDOUR.PresentationInfo.Flag.AudioBus,ARDOUR.PresentationInfo.max_order):front()
 r:input():disconnect_all();return r
end
local function add(r,uri,preset,vst,index)
 local p=ARDOUR.LuaAPI.new_plugin(s,uri,vst and ARDOUR.PluginType.VST3 or ARDOUR.PluginType.LV2,preset or '')
 assert(not p:isnil(),uri);assert(r:add_processor_by_index(p,index or 0,nil,true)==0,uri)
 return p
end
local function linkio(src,dst)
 for i=0,math.min(src:n_ports():n_audio(),dst:n_ports():n_audio())-1 do
  assert(src:audio(i):connect(dst:audio(i):name())==0, 'connect '..src:audio(i):name())
 end
end
local fat='http://gareus.org/oss/lv2/fat1'
local rb='http://breakfastquay.com/rdf/lv2-rubberband#stereo'
local voices={}
for i,label in ipairs({'A','B'}) do
 local v=bus('VOIX '..label);voices[i]=v
 add(v,fat,'ProControl - Voix discrete chromatique'):deactivate()
 for _,interval in ipairs({'Quinte +7','Octave -12'}) do
  local h=bus('HARM '..label..' '..interval)
  local p=add(h,rb,'ProControl - '..interval..' stereo')
  s:add_internal_send(h,v:amp(),v)
  h:gain_control():set_value(.12589254,PBD.GroupControlDisposition.NoGroup)
  p:deactivate() -- high latency: explicitly enable for comparison
  h:mute_control():set_value(1,PBD.GroupControlDisposition.NoGroup)
 end
end
local mod=bus('VOC MOD');mod:output():disconnect_all()
for _,v in ipairs(voices) do s:add_internal_send(mod,v:amp(),v) end
local voc=bus('VOCODEUR')
local fx=add(voc,'ABCDEF019182FAEB566D624153465854','ProControl - Vocodeur 20 bandes',true)
assert(voc:add_sidechain(fx),'vocoder sidechain');linkio(mod:output(),fx:to_insert():sidechain_input())
voc:gain_control():set_value(.12589254,PBD.GroupControlDisposition.NoGroup)
fx:deactivate()
local midi=s:new_midi_track(ARDOUR.ChanCount(ARDOUR.DataType('midi'),1),ARDOUR.ChanCount(ARDOUR.DataType('audio'),2),true,ARDOUR.LuaAPI.new_plugin_info('ABCDEF019182FAEB566D624153675854',ARDOUR.PluginType.VST3),nil,ARDOUR.RouteGroup(),1,'VOC ACCORDS',ARDOUR.PresentationInfo.max_order,ARDOUR.TrackMode.Normal,false):front()
midi:nth_plugin(0):deactivate()
midi:output():disconnect_all();linkio(midi:output(),voc:input())
local kick=bus('KICK');local sc=bus('KICK SC');sc:output():disconnect_all()
s:add_internal_send(sc,kick:amp(),kick)
local pump=bus('PUMP')
local comp=add(pump,'http://lsp-plug.in/plugins/lv2/sc_compressor_stereo','ProControl - Pump kick externe stereo')
comp:deactivate()
assert(pump:add_sidechain(comp),'pump sidechain');linkio(sc:output(),comp:to_insert():sidechain_input())
local sh=add(pump,'https://www.jahnichen.de/plugins/lv2/BShapr','ProControl - Pump 1 temps',false,1);sh:deactivate()
local tr=add(kick,'http://lsp-plug.in/plugins/lv2/beat_breather_stereo','ProControl - Transitoires neutres stereo');tr:deactivate()
sleep(1)
-- Route creation auto-connects asynchronously. Apply final exclusive paths
-- after all plugin I/O has settled, then verify them in the saved state.
mod:output():disconnect_all();linkio(mod:output(),fx:to_insert():sidechain_input())
midi:output():disconnect_all();linkio(midi:output(),voc:input())
sc:output():disconnect_all();linkio(sc:output(),comp:to_insert():sidechain_input())
-- LSP's LV2 sidechain group is not automatically wired by Ardour 9.8.
local pins=comp:to_insert():input_map(0)
pins:set(ARDOUR.DataType('audio'),2,2);pins:set(ARDOUR.DataType('audio'),3,2)
comp:to_insert():set_input_map(0,pins)
-- Ardour creates internal sends at -inf. Set the seven new sends to unity;
-- harmony levels are controlled by their muted return faders.
for _,source in ipairs({voices[1], voices[2], kick}) do
 for i=0,8 do
  local p=source:nth_send(i);if p:isnil() then break end
  p:to_send():gain_control():set_value(1,PBD.GroupControlDisposition.NoGroup)
 end
end
sleep(.2)
for r in s:get_routes():iter() do
 for i=0,64 do
  local p=r:nth_plugin(i);if p:isnil() then break end
  report:write(r:name(),'\t',p:name(),'\t',p:signal_latency(),'\n')
 end
end

end
