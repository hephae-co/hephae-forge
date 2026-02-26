import React from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Label } from 'recharts';

interface RadialScoreProps {
  score: number;
  size?: number;
  label?: string;
  color?: string;
}

const RadialScore: React.FC<RadialScoreProps> = ({ score, size = 200, label = "Score", color }) => {
  const data = [
    { name: 'Score', value: score },
    { name: 'Remaining', value: 100 - score },
  ];

  const getColor = (s: number) => {
    if (color) return color;
    if (s >= 90) return '#22c55e'; // green-500
    if (s >= 70) return '#eab308'; // yellow-500
    return '#ef4444'; // red-500
  };

  const activeColor = getColor(score);
  const inactiveColor = '#e5e7eb'; // gray-200

  return (
    <div className="relative flex flex-col items-center justify-center" style={{ width: size, height: size }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          {/* Fixed: Moved cornerRadius from Cell to Pie as Cell does not support it */}
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius="80%"
            outerRadius="100%"
            startAngle={180}
            endAngle={0}
            paddingAngle={0}
            dataKey="value"
            cornerRadius={10}
          >
            <Cell key="score" fill={activeColor} />
            <Cell key="remaining" fill={inactiveColor} stroke="none" />
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/3 text-center">
        <span className="text-4xl font-bold text-gray-800 dark:text-white block">{score}</span>
        <span className="text-xs text-gray-500 uppercase tracking-wider font-semibold">{label}</span>
      </div>
    </div>
  );
};

export default RadialScore;