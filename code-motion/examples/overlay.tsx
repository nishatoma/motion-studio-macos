import React from 'react';
import {AbsoluteFill,useCurrentFrame,useVideoConfig,spring,interpolate} from 'remotion';
export const Scene=()=>{
 const frame=useCurrentFrame();const {width,height,fps,durationInFrames}=useVideoConfig();const s=spring({frame:frame-3,fps,config:{damping:20,stiffness:130}});const opacity=interpolate(frame,[durationInFrames-12,durationInFrames-1],[1,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
 return <AbsoluteFill style={{backgroundColor:'transparent',justifyContent:'center',alignItems:'center',opacity,fontFamily:'Arial'}}>
 <div style={{display:'flex',gap:32,alignItems:'center',transform:`translateY(${(1-s)*60}px) scale(${.85+s*.15})`}}>
 <svg width={width*.18} height={height*.22} viewBox="0 0 230 150"><rect x="6" y="6" width="218" height="138" rx="18" fill="#102332" stroke="#62e6d5" strokeWidth="5"/><rect x="6" y="35" width="218" height="28" fill="#62e6d5"/><rect x="28" y="88" width="40" height="27" rx="4" fill="#f6c76b"/></svg>
 <div style={{fontSize:width*.075,fontWeight:700,color:'#eef7fb'}}>$500</div>
 <svg width="85" height="110" viewBox="0 0 85 110" style={{transform:`translateY(${interpolate(frame,[8,36],[0,15],{extrapolateLeft:'clamp',extrapolateRight:'clamp'})}px)`}}><path d="M42 10 V85 M15 60 L42 88 L70 60" fill="none" stroke="#ff8a78" strokeWidth="9" strokeLinecap="round" strokeLinejoin="round"/></svg>
 </div></AbsoluteFill>;
};
