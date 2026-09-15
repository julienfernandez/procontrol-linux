ardour {
  ["type"] = "EditorHook",
  name = "ProControl Stereo Meters",
  author = "ProControl Linux",
  description = "Read existing audio meters and send independent channels to the local ProControl daemon. No audio processing or routing changes."
}
function signals ()
  return LuaSignal.Set():add ({[LuaSignal.LuaTimerDS] = true})
end
function factory ()
  local tx = ARDOUR.LuaOSC.Address ("osc.udp://127.0.0.1:3820")
  local gen, seq, ticks = os.time(), 0, 0
  local previous, last_session = "", ""
  local function kind(s)
    if s:is_master() then return "MA" end
    if s:is_monitor() then return "MO" end
    local flags=s:presentation_info_ptr():flags()
    local F=ARDOUR.PresentationInfo.Flag
    if (flags & F.AudioTrack) ~= 0 then return "AT" end
    if (flags & F.MidiTrack) ~= 0 then return "MT" end
    if (flags & F.VCA) ~= 0 then return "V" end
    if (flags & F.AudioBus) ~= 0 then return "B" end
    if (flags & F.MidiBus) ~= 0 then return "MB" end
    return "OTHER"
  end
  return function ()
    if not Session then return end
    local session=Session:path()
    if session~=last_session then previous="";gen=gen+1;last_session=session end
    local rows, sig = {}, {}
    for s in Session:get_stripables():iter() do
      local r=s:to_route(); local m=nil; local audio,midi=0,0
      if not r:isnil() then
        m=r:peak_meter()
        if not m:isnil() then
          local streams=m:input_streams()
          audio=math.min(64,streams:n_audio());midi=streams:n_midi()
        end
      end
      local row={id=s:to_stateful():id():to_s(), name=s:name(), kind=kind(s),
                 order=s:presentation_info_ptr():order(),hidden=s:is_hidden() and 1 or 0,
                 channels=audio,midi=midi,meter=m}
      rows[#rows+1]=row
      sig[#sig+1]=table.concat({row.id,row.name,row.kind,row.order,row.hidden,audio},"\31")
    end
    table.sort(sig);local signature=table.concat(sig,"\30")
    ticks=ticks+1
    if signature~=previous then gen=gen+1;previous=signature;ticks=10 end
    if ticks>=10 then
      ticks=0;tx:send('/procontrol/catalog/begin','sii',session,gen,#rows)
      for _,r in ipairs(rows) do
        tx:send('/procontrol/catalog/route','sisissii',session,gen,r.id,r.order,r.kind,r.name,r.channels,r.hidden)
      end
      tx:send('/procontrol/catalog/end','si',session,gen)
    end
    seq=seq+1
    for _,r in ipairs(rows) do
      local values={session,gen,seq,r.id}
      for ch=0,r.channels-1 do
        local db=r.meter:meter_level(r.midi+ch,ARDOUR.MeterType.MeterPeak)
        if db~=db or db==-math.huge then db=-193 end
        if db==math.huge then db=40 end
        values[#values+1]=math.max(-193,math.min(40,db))
      end
      tx:send('/procontrol/meter','siis'..string.rep('f',r.channels),table.unpack(values))
    end
  end
end
