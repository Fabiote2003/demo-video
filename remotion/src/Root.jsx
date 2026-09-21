import React from 'react';
import {Composition} from 'remotion';
import {Intro, Badge} from './Intro';

const CLUB = {
  club: 'Club',
  logo: 'logo.png',
};

export const RemotionRoot = () => (
  <>
    <Composition
      id="Intro"
      component={Intro}
      durationInFrames={90}
      fps={30}
      width={1920}
      height={1080}
      defaultProps={CLUB}
    />
    <Composition
      id="Badge"
      component={Badge}
      durationInFrames={1}
      fps={30}
      width={560}
      height={130}
      defaultProps={CLUB}
    />
  </>
);
