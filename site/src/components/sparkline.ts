/**
 * An SVG path through the values, scaled into a width by height box with y growing down.
 * A null breaks the line, so a quarter with no figure is not drawn as if it had one.
 */
export function sparkPath(
  values: readonly (number | null)[],
  width: number,
  height: number,
  domain: readonly [number, number],
): string {
  const [low, high] = domain;
  if (!(high > low)) throw new RangeError('a sparkline domain must have high above low');
  const step = values.length > 1 ? width / (values.length - 1) : 0;
  let path = '';
  let drawing = false;
  values.forEach((value, index) => {
    if (value === null) {
      drawing = false;
      return;
    }
    const x = (index * step).toFixed(1);
    const y = (height - ((value - low) / (high - low)) * height).toFixed(1);
    path += `${drawing ? 'L' : 'M'}${x} ${y}`;
    drawing = true;
  });
  return path;
}
