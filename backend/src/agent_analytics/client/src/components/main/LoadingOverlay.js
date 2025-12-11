import { Loading } from '../CarbonComponents';

export const LoadingOverlay = ({ isLoading }) => {
  if (!isLoading) return null;

  return (
    <div className="absolute inset-0 bg-white bg-opacity-70 flex items-center justify-center z-50 transition-opacity duration-200">
      <Loading withOverlay={false} description="Loading..." />
    </div>
  );
};
