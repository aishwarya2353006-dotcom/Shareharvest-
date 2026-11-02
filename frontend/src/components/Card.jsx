import React from 'react';

const Card = ({ 
  title,
  children,
  footer,
  className = '',
  padded = true,
  ...props
}) => {
  return (
    <div className={`card ${padded ? 'card-padded' : ''} ${className}`} {...props}>
      {title && <div className="card-header"><h3 className="card-title">{title}</h3></div>}
      <div className="card-body">{children}</div>
      {footer && <div className="card-footer">{footer}</div>}
    </div>
  );
};

export default Card;
