import { FC, ReactNode } from 'react';
import { PanelSectionRow, DialogButton, Field, Focusable } from 'decky-frontend-lib';

interface SnapshotSectionRowProps {
    icon: ReactNode;
    buttonText: string;
    disabled?: boolean;
    onClick?: (e: MouseEvent) => void;
    label?: ReactNode;
    description?: ReactNode;
    additionalButtonIcon?: ReactNode;
    additionalButtonOnClick?: (e: MouseEvent) => void;
}

const SnapshotSectionRow: FC<SnapshotSectionRowProps> = ({ icon, buttonText, disabled, onClick, label, description, additionalButtonIcon, additionalButtonOnClick }) => (
    <PanelSectionRow>
        <Field
            bottomSeparator="none"
            icon={null}
            label={null}
            childrenLayout={undefined}
            inlineWrap="keep-inline"
            padding="none"
            spacingBetweenLabelAndChild="none"
            childrenContainerWidth="max"
        >
            <Focusable style={{ display: 'flex', flexWrap:'wrap', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                <div style={{ display: 'flex', fontSize: '1em', justifyContent: 'center', alignItems: 'center', marginRight: '.5em' }}>
                    <div style={{ fontSize: '1em', display: 'flex', alignItems: 'center', height: '100%' }}>{icon}</div>
                    <span style={{ marginLeft: '.5em', fontSize: '1em' }}>{label}</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center' }}>
                    <DialogButton onClick={onClick}
                        disabled={disabled}
                        style={{ padding: '10px', fontSize: '14px' }}
                    >
                        {buttonText}
                    </DialogButton>
                    {additionalButtonIcon && (
                        <DialogButton
                            onClick={additionalButtonOnClick}
                            style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '10px', maxWidth: '40px', minWidth: 'auto', marginLeft: '.5em' }}
                        >
                            {additionalButtonIcon}
                        </DialogButton>
                    )}
                </div>
                <div style={{ marginTop: '.5em', fontSize: '0.7em', width: '100%' }}>
                    {description}
                </div>
            </Focusable>
        </Field>
    </PanelSectionRow>
);


export default SnapshotSectionRow;
