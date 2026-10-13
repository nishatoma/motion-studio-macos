import React from 'react';
import {AbsoluteFill,useCurrentFrame,useVideoConfig,spring,interpolate} from 'remotion';
export const Scene=()=>{
 const frame=useCurrentFrame();const {width,height,fps,durationInFrames}=useVideoConfig();
 const words=['THE COST','OF LIVING'];const exit=interpolate(frame,[durationInFrames-18,durationInFrames-1],[1,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
 return <AbsoluteFill style={{backgroundColor:'#07131f',color:'#eef7fb',justifyContent:'center',padding:width*.08,fontFamily:'Arial',opacity:exit,transform:`scale(${1+frame/durationInFrames*.035})`}}>
  <div style={{fontSize:width*.017,letterSpacing:6,color:'#9aafbd',marginBottom:height*.06}}>A DOCUMENTARY ABOUT ORDINARY LIFE</div>
  {words.map((word,i)=>{const s=spring({frame:frame-i*14,fps,config:{damping:22,stiffness:110}});return <div key={word} style={{overflow:'hidden',fontSize:width*.09,lineHeight:1.04,fontWeight:800,letterSpacing:-width*.004}}><div style={{transform:`translateY(${(1-s)*120}%)`,color:i?'#f6c76b':'#eef7fb'}}>{word}</div></div>})}
  <div style={{height:3,width:width*.4*interpolate(frame,[36,70],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'}),backgroundColor:'#62e6d5',marginTop:height*.06}}/>
 </AbsoluteFill>;
};
