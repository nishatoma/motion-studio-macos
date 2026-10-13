import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate, spring} from 'remotion';
export const Scene = () => {
  const frame=useCurrentFrame(); const {width,height,fps,durationInFrames}=useVideoConfig();
  const progress=interpolate(frame,[12,durationInFrames-24],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const enter=spring({frame,fps,config:{damping:24,stiffness:120}});
  const points=Array.from({length:101},(_,i)=>{const t=i/100;return `${140+t*1000},${580-(Math.exp(t*3)-1)/(Math.exp(3)-1)*350}`}).join(' ');
  const amount=Math.round((Math.exp(progress*3)-1)/(Math.exp(3)-1)*1000000); const year=Math.round(progress*35);
  return <AbsoluteFill style={{backgroundColor:'#07131f',fontFamily:'Arial',color:'#eef7fb'}}>
    <div style={{width:1280,height:720,transform:`scale(${width/1280},${height/720})`,transformOrigin:'top left',position:'absolute'}}>
      <div style={{position:'absolute',left:100,top:65,fontSize:26,letterSpacing:3,opacity:enter}}>35 YEARS OF GROWTH</div>
      <div style={{position:'absolute',left:100,top:112,fontSize:72,fontWeight:700,fontVariantNumeric:'tabular-nums',transform:`translateY(${(1-enter)*25}px)`}}>${amount.toLocaleString('en-US')}</div>
      <svg width="1280" height="720" style={{position:'absolute',left:0,top:0}}>
        <defs><clipPath id="reveal"><rect x="138" y="225" width={1006*progress} height="365" /></clipPath></defs>
        <line x1="140" y1="580" x2="1140" y2="580" stroke="#365261" strokeWidth="2"/>
        <line x1="140" y1="230" x2="140" y2="580" stroke="#365261" strokeWidth="2"/>
        <polyline points={points} fill="none" stroke="#62e6d5" strokeWidth="6" clipPath="url(#reveal)"/>
        <circle cx={140+progress*1000} cy={580-(Math.exp(progress*3)-1)/(Math.exp(3)-1)*350} r="8" fill="#f6c76b"/>
        <text x="96" y="587" fill="#9aafbd" fontSize="20">$0</text><text x="50" y="240" fill="#9aafbd" fontSize="20">$1M</text>
        <text x={140+progress*1000} y="620" fill="#f6c76b" fontSize="24" textAnchor="middle">Year {year}</text>
      </svg>
      <div style={{position:'absolute',left:100,bottom:35,color:'#9aafbd',fontSize:18}}>Illustrative growth curve · no assumed investment return</div>
    </div>
  </AbsoluteFill>;
};
