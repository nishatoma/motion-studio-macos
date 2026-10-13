import React from 'react';
import {AbsoluteFill,useCurrentFrame,useVideoConfig,spring} from 'remotion';
export const Scene=()=>{
 const frame=useCurrentFrame();const {fps,width}=useVideoConfig();
 const events=[{time:.5,label:'TITLE',color:'#62e6d5'},{time:2,label:'IMPACT',color:'#f6c76b'},{time:4,label:'REVEAL',color:'#ff8a78'}];
 return <AbsoluteFill style={{backgroundColor:'#07131f',justifyContent:'center',alignItems:'center',fontFamily:'Arial'}}>
 <div style={{display:'flex',gap:width*.03}}>{events.map(event=>{const start=Math.round(event.time*fps);const s=spring({frame:frame-start,fps,config:{damping:22}});return <div key={event.label} style={{color:event.color,opacity:frame>=start?1:0,transform:`scale(${s})`,fontSize:width*.055,fontWeight:800}}>{event.label}</div>})}</div>
 </AbsoluteFill>;
};
