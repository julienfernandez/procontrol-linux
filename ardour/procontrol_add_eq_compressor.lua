ardour { ["type"]="EditorAction", name="ProControl - Add EQ and Compressor" }
function factory() return function()
local settings = {
["para_equalizer_x8_mono"]={[16]=1,[21]=60,[23]=1,[27]=1,[32]=120,[34]=1,[38]=1,[43]=250,[45]=1,[49]=1,[54]=500,[56]=1,[60]=1,[65]=1000,[67]=1,[71]=1,[76]=2000,[78]=1,[82]=1,[87]=4000,[89]=1,[93]=1,[98]=8000,[100]=1},
["para_equalizer_x8_stereo"]={[21]=1,[26]=60,[28]=1,[32]=1,[37]=120,[39]=1,[43]=1,[48]=250,[50]=1,[54]=1,[59]=500,[61]=1,[65]=1,[70]=1000,[72]=1,[76]=1,[81]=2000,[83]=1,[87]=1,[92]=4000,[94]=1,[98]=1,[103]=8000,[105]=1},
["compressor_mono"]={[20]=1.0},
["compressor_stereo"]={[23]=1.0},
}
assert(Session, "No session")
assert(not Session:transport_rolling(), "Stop playback before adding plugins")
local plans={}
for r in Session:get_tracks():iter() do
 if not r:to_track():to_audio_track():isnil() then
  local ch=r:n_inputs():n_audio()
  assert(ch==1 or ch==2, "Unsupported channel count: "..r:name())
  local suffix=ch==1 and "mono" or "stereo"
  local existing={}
  for i=0,1023 do
   local p=r:nth_plugin(i);if p:isnil() then break end
   existing[p:to_insert():plugin(0):unique_id()]=true
  end
  local pos=0
  for _,base in ipairs({"para_equalizer_x8", "compressor"}) do
   local name=base.."_"..suffix;local uri="http://lsp-plug.in/plugins/lv2/"..name
   if not existing[uri] then
    local p=ARDOUR.LuaAPI.new_plugin(Session,uri,ARDOUR.PluginType.LV2,"")
    assert(not p:isnil(), "Missing plugin: "..name)
    for k,v in pairs(settings[name]) do assert(ARDOUR.LuaAPI.set_processor_param(p,k,v), "Parameter "..k) end
    plans[#plans+1]={route=r,processor=p,pos=pos,name=name}
   end
   pos=pos+1
  end
 end
end
for _,p in ipairs(plans) do
 local result=p.route:add_processor_by_index(p.processor,p.pos,nil,true)
 assert(result==0, "Insert failed: "..p.route:name())
 print("Added",p.route:name(),p.name)
end
Session:save_state("",false,false,false)
print("PROCONTROL DSP READY", #plans, "plugins added")

end end
